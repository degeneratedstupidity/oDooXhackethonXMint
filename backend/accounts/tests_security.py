"""Tests for the two security foundations: tenant isolation and encryption at rest."""

from datetime import date

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
