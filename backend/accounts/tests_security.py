"""Tests for the two security foundations: tenant isolation and encryption at rest."""

from datetime import date

from django.core.cache import cache
from django.db import connection, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from attendance.models import Attendance
from django.utils import timezone

from .models import BankDetail, EmployeeProfile, Role, User
from .tenancy import set_current_company
from .tests import make_company, make_user


class RowLevelSecurityTests(TestCase):
    """Postgres must refuse to return another company's rows, not merely the API.

    These run against real policies — the test database is built by the same migrations,
    and Django connects as the same non-superuser role, so a regression here is a real
    regression.
    """

    def setUp(self):
        self.odoo = make_company("Odoo India")
        self.odoo_user = make_user(self.odoo, "John", "Doe")

        self.rival = make_company("Rival Corp")
        self.rival_user = make_user(self.rival, "Eve", "Adams")

    def test_a_company_sees_only_its_own_profiles(self):
        with transaction.atomic():
            set_current_company(self.odoo.id)
            visible = list(EmployeeProfile.objects.values_list("user__login_id", flat=True))
        self.assertEqual(visible, [self.odoo_user.login_id])

    def test_explicitly_querying_another_company_returns_nothing(self):
        """Even naming the other company's id must not leak a row."""
        with transaction.atomic():
            set_current_company(self.rival.id)
            leaked = EmployeeProfile.objects.filter(company=self.odoo).count()
        self.assertEqual(leaked, 0)

    def test_no_scope_returns_no_rows(self):
        """A query with no company set is not a query for everything."""
        with transaction.atomic():
            set_current_company(None)
            self.assertEqual(EmployeeProfile.objects.count(), 0)

    def test_attendance_is_isolated_between_companies(self):
        with transaction.atomic():
            set_current_company(self.odoo.id)
            Attendance.objects.create(
                company=self.odoo,
                user=self.odoo_user,
                date=date(2026, 6, 1),
                check_in=timezone.now(),
            )

        with transaction.atomic():
            set_current_company(self.rival.id)
            self.assertEqual(Attendance.objects.count(), 0)

    def test_writing_into_another_company_is_refused(self):
        """The policy's WITH CHECK must block a mislabelled insert."""
        with self.assertRaises(Exception):
            with transaction.atomic():
                set_current_company(self.rival.id)
                EmployeeProfile.objects.create(company=self.odoo, user=self.odoo_user)


class TenantApiIsolationTests(TestCase):
    def setUp(self):
        self.odoo = make_company("Odoo India")
        self.odoo_user = make_user(self.odoo, "John", "Doe")
        self.rival = make_company("Rival Corp")
        self.rival_user = make_user(self.rival, "Eve", "Adams")
        self.client = APIClient()

    def test_directory_lists_only_the_callers_company(self):
        self.client.force_authenticate(user=self.rival_user)
        response = self.client.get("/api/employees/")
        login_ids = [row["login_id"] for row in response.data]
        self.assertEqual(login_ids, [self.rival_user.login_id])

    def test_fetching_another_companys_employee_by_id_is_not_found(self):
        self.client.force_authenticate(user=self.rival_user)
        response = self.client.get(f"/api/employees/{self.odoo_user.id}/")
        self.assertEqual(response.status_code, 404)


class EncryptionTests(TestCase):
    """Bank and statutory identifiers must be ciphertext in the database."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)

    def test_values_are_encrypted_in_the_database_but_readable_through_the_orm(self):
        with transaction.atomic():
            set_current_company(self.company.id)
            BankDetail.objects.create(
                company=self.company,
                user=self.user,
                account_number="123456789012",
                pan_number="ABCDE1234F",
            )

            fetched = BankDetail.objects.get(user=self.user)
            self.assertEqual(fetched.account_number, "123456789012")
            self.assertEqual(fetched.pan_number, "ABCDE1234F")

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT account_number, pan_number FROM accounts_bankdetail WHERE user_id = %s",
                    [self.user.id],
                )
                raw_account, raw_pan = cursor.fetchone()

        self.assertNotIn("123456789012", raw_account)
        self.assertNotIn("ABCDE1234F", raw_pan)
        # Fernet ciphertext is versioned and starts with a known prefix.
        self.assertTrue(raw_account.startswith("gAAAAA"), raw_account[:20])

    def test_blank_values_are_left_alone(self):
        with transaction.atomic():
            set_current_company(self.company.id)
            detail = BankDetail.objects.create(company=self.company, user=self.user)
            self.assertEqual(BankDetail.objects.get(pk=detail.pk).account_number, "")


class RolePermissionTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, "Asha", "Menon", role=Role.ADMIN)
        self.hr = make_user(self.company, "Rahul", "Verma", role=Role.HR_OFFICER)
        self.employee = make_user(self.company, "Priya", "Nair", role=Role.EMPLOYEE)
        self.client = APIClient()

    def new_employee_payload(self, email):
        return {
            "first_name": "New",
            "last_name": "Person",
            "email": email,
            "date_of_joining": "2026-01-01",
        }

    def test_admin_can_add_an_employee(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/employees/", self.new_employee_payload("a@x.test"), format="json"
        )
        self.assertEqual(response.status_code, 201)
        # The generated credentials are returned once, for the administrator to pass on.
        self.assertIn("credentials", response.data)

    def test_hr_officer_can_add_an_employee(self):
        self.client.force_authenticate(user=self.hr)
        response = self.client.post(
            "/api/employees/", self.new_employee_payload("b@x.test"), format="json"
        )
        self.assertEqual(response.status_code, 201)

    def test_employee_cannot_add_an_employee(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.post(
            "/api/employees/", self.new_employee_payload("c@x.test"), format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_employee_cannot_edit_someone_elses_profile(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.patch(
            f"/api/employees/{self.admin.id}/", {"phone": "1234567890"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_employee_can_edit_their_own_profile(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.patch(
            f"/api/employees/{self.employee.id}/", {"phone": "1234567890"}, format="json"
        )
        self.assertEqual(response.status_code, 200)

    def test_nobody_changes_their_own_role(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            f"/api/employees/{self.admin.id}/", {"role": "employee"}, format="json"
        )
        self.assertEqual(response.status_code, 403)


class PrivateInfoVisibilityTests(TestCase):
    """Who may read the private half of a profile.

    The directory is open to everyone — that is the point of a directory — but date of
    birth, home address, personal email and bank details are not directory information.
    An employee sees those on their own record only; Admin and HR see them on anyone's,
    because administering people requires them.
    """

    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, "Asha", "Menon", role=Role.ADMIN)
        self.hr = make_user(self.company, "Rahul", "Verma", role=Role.HR_OFFICER)
        self.employee = make_user(self.company, "Priya", "Nair", role=Role.EMPLOYEE)
        self.colleague = make_user(self.company, "Arjun", "Das", role=Role.EMPLOYEE)

        set_current_company(self.company.id)
        for person in (self.admin, self.hr, self.employee, self.colleague):
            EmployeeProfile.objects.filter(user=person).update(
                job_position="Engineer",
                date_of_birth=date(1990, 5, 1),
                residing_address="12 Residency Road",
                personal_email=f"{person.first_name.lower()}@personal.test",
                about="Builds things.",
            )
            BankDetail.objects.create(
                company=self.company,
                user=person,
                bank_name="State Bank",
                account_number="12345678901",
                pan_number="ABCDE1234F",
            )

        self.client = APIClient()

    def get_colleague(self, viewer):
        self.client.force_authenticate(user=viewer)
        response = self.client.get(f"/api/employees/{self.colleague.id}/")
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_employee_viewing_a_colleague_sees_no_bank_details(self):
        data = self.get_colleague(self.employee)
        self.assertNotIn("bank_detail", data)

    def test_employee_viewing_a_colleague_sees_no_private_information(self):
        profile = self.get_colleague(self.employee)["profile"]
        for field in (
            "date_of_birth",
            "residing_address",
            "personal_email",
            "gender",
            "marital_status",
            "nationality",
        ):
            self.assertNotIn(field, profile)

    def test_employee_viewing_a_colleague_still_sees_work_info_and_resume(self):
        """Trimming the private block must not empty the page it is trimmed from."""
        profile = self.get_colleague(self.employee)["profile"]
        self.assertEqual(profile["job_position"], "Engineer")
        self.assertEqual(profile["about"], "Builds things.")

    def test_employee_sees_everything_on_their_own_record(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(f"/api/employees/{self.employee.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("bank_detail", response.data)
        self.assertEqual(response.data["profile"]["residing_address"], "12 Residency Road")

    def test_admin_sees_everything_on_anyones_record(self):
        data = self.get_colleague(self.admin)
        self.assertIn("bank_detail", data)
        self.assertEqual(data["bank_detail"]["pan_number"], "ABCDE1234F")
        self.assertEqual(data["profile"]["residing_address"], "12 Residency Road")

    def test_hr_officer_sees_everything_on_anyones_record(self):
        data = self.get_colleague(self.hr)
        self.assertIn("bank_detail", data)
        self.assertEqual(data["profile"]["date_of_birth"], "1990-05-01")


class TenantScopeOnPlainViewsTests(TestCase):
    """Views that are not viewsets still need the company scope set.

    Without it, row-level security hides the caller's own profile row and the response
    comes back with the profile fields empty — which is what happened before MeView was
    given the scoping mixin.
    """

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company, "Asha", "Menon", role=Role.ADMIN)
        profile = EmployeeProfile.objects.get(user=self.user)
        profile.job_position = "Chief People Officer"
        profile.department = "Leadership"
        profile.save()
        # Re-fetch so the request sees the saved profile rather than the relation cached
        # on the object created in make_user.
        self.user = User.objects.get(pk=self.user.pk)
        self.client = APIClient()

    def test_me_returns_the_callers_profile_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/me/")
        self.assertEqual(response.data["job_position"], "Chief People Officer")
        self.assertEqual(response.data["department"], "Leadership")


class DeactivationTests(TestCase):
    """Leaving the company must not erase the record of what someone was paid."""

    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, "Asha", "Menon", role=Role.ADMIN)
        self.employee = make_user(self.company, "Priya", "Nair", role=Role.EMPLOYEE)
        Attendance.objects.create(
            company=self.company,
            user=self.employee,
            date=date(2026, 6, 1),
            check_in=timezone.now(),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_deactivating_keeps_the_attendance_history(self):
        self.client.delete(f"/api/employees/{self.employee.id}/")
        self.assertEqual(Attendance.objects.filter(user=self.employee).count(), 1)

    def test_deactivating_keeps_the_user_record(self):
        self.client.delete(f"/api/employees/{self.employee.id}/")
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)
        self.assertIsNotNone(self.employee.deactivated_on)

    def test_a_former_employee_is_hidden_from_the_directory(self):
        self.client.delete(f"/api/employees/{self.employee.id}/")
        listed = [row["id"] for row in self.client.get("/api/employees/").data]
        self.assertNotIn(self.employee.id, listed)

    def test_a_former_employee_can_still_be_listed_on_request(self):
        self.client.delete(f"/api/employees/{self.employee.id}/")
        listed = [row["id"] for row in self.client.get("/api/employees/?include_inactive=true").data]
        self.assertIn(self.employee.id, listed)

    def test_a_former_employee_can_be_reactivated(self):
        """Their record has to stay reachable by id, or reactivation is impossible."""
        self.client.delete(f"/api/employees/{self.employee.id}/")
        response = self.client.post(f"/api/employees/{self.employee.id}/reactivate/")
        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.is_active)

    def test_nobody_deactivates_themselves(self):
        response = self.client.delete(f"/api/employees/{self.admin.id}/")
        self.assertEqual(response.status_code, 403)

    def test_an_employee_cannot_deactivate_anyone(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.delete(f"/api/employees/{self.admin.id}/")
        self.assertEqual(response.status_code, 403)


class RelativeMediaUrlTests(TestCase):
    """File URLs must resolve from a browser, not only from inside the Docker network."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company, "Asha", "Menon", role=Role.ADMIN)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_an_avatar_url_is_a_path_not_an_absolute_url(self):
        self.user.avatar = "avatars/example.png"
        self.user.save(update_fields=["avatar"])
        avatar = self.client.get("/api/me/").data["avatar"]
        self.assertTrue(avatar.startswith("/media/"), avatar)
        self.assertNotIn("http://", avatar)

    def test_a_missing_avatar_is_null(self):
        self.assertIsNone(self.client.get("/api/me/").data["avatar"])


class LoginThrottleTests(TestCase):
    """Login IDs follow a published format, so password guessing must be bounded."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company, "Asha", "Menon", role=Role.ADMIN)
        self.client = APIClient()
        cache.clear()

    def tearDown(self):
        # Throttle state lives in the cache; leaving it set would affect other tests.
        cache.clear()

    def attempt(self, password):
        return self.client.post(
            "/api/auth/login/",
            {"login_id": self.user.login_id, "password": password},
            format="json",
        )

    def test_repeated_failures_are_eventually_throttled(self):
        statuses = [self.attempt("wrong").status_code for _ in range(12)]
        self.assertIn(429, statuses)

    def test_the_limit_allows_a_reasonable_number_of_mistakes(self):
        """Someone mistyping a few times must not be locked out."""
        for _ in range(5):
            self.assertEqual(self.attempt("wrong").status_code, 401)
        self.assertEqual(self.attempt("Str0ngPass!2026").status_code, 200)
