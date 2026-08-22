from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Company, EmployeeProfile, Role, User
from .seed import seed_default_time_off_types
from .tenancy import set_current_company


def make_company(name="Odoo India"):
    company = Company.objects.create(name=name, code=Company.derive_code(name))
    set_current_company(company.id)
    seed_default_time_off_types(company)
    return company


def make_user(company, first="John", last="Doe", role=Role.ADMIN, joining=date(2022, 1, 1)):
    user = User.objects.create_user(
        login_id=User.generate_login_id(company, first, last, joining.year),
        email=f"{first.lower()}@example.com",
        password="Str0ngPass!2026",
        company=company,
        first_name=first,
        last_name=last,
        role=role,
        date_of_joining=joining,
    )
    EmployeeProfile.objects.create(company=company, user=user)
    return user


class CompanyCodeTests(TestCase):
    def test_two_word_name_uses_both_initials(self):
        self.assertEqual(Company.derive_code("Odoo India"), "OI")

    def test_single_word_name_uses_first_two_letters(self):
        self.assertEqual(Company.derive_code("Acme"), "AC")

    def test_short_single_word_name_is_padded(self):
        self.assertEqual(Company.derive_code("X"), "XX")


class LoginIdTests(TestCase):
    """The format from the specification: OIJODO20220001."""

    def setUp(self):
        self.company = make_company()

    def test_matches_the_specifications_example(self):
        login_id = User.generate_login_id(self.company, "John", "Doe", 2022)
        self.assertEqual(login_id, "OIJODO20220001")

    def test_sequence_increments_within_a_year(self):
        make_user(self.company, "John", "Doe", joining=date(2022, 5, 1))
        second = User.generate_login_id(self.company, "Jane", "Smith", 2022)
        self.assertEqual(second, "OIJASM20220002")

    def test_sequence_restarts_each_year(self):
        make_user(self.company, "John", "Doe", joining=date(2022, 5, 1))
        next_year = User.generate_login_id(self.company, "Jane", "Smith", 2023)
        self.assertTrue(next_year.endswith("0001"), next_year)

    def test_short_names_are_padded_to_four_characters(self):
        login_id = User.generate_login_id(self.company, "Al", "B", 2024)
        self.assertEqual(login_id, "OIALBX20240001")

    def test_sequence_skips_an_id_already_taken(self):
        """A removed and re-added employee must not collide with an existing login ID."""
        make_user(self.company, "John", "Doe", joining=date(2022, 5, 1))
        # A second person joining the same year would be 0002; occupy it directly.
        User.objects.create_user(
            login_id="OIJASM20220002",
            email="jane@example.com",
            password="x",
            company=self.company,
            first_name="Jane",
            last_name="Smith",
            date_of_joining=date(2022, 6, 1),
        )
        third = User.generate_login_id(self.company, "Jane", "Smith", 2022)
        self.assertEqual(third, "OIJASM20220003")


class PasswordTests(TestCase):
    def test_generated_password_is_not_predictable(self):
        passwords = {User.generate_password() for _ in range(50)}
        self.assertEqual(len(passwords), 50)

    def test_password_is_stored_hashed(self):
        company = make_company()
        user = make_user(company)
        self.assertNotIn("Str0ngPass!2026", user.password)
        self.assertTrue(user.check_password("Str0ngPass!2026"))


class SignUpApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_sign_up_creates_company_and_admin(self):
        response = self.client.post(
            "/api/auth/signup/",
            {
                "company_name": "Odoo India",
                "name": "John Doe",
                "email": "john@odoo.test",
                "password": "Str0ngPass!2026",
                "confirm_password": "Str0ngPass!2026",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["user"]["role"], Role.ADMIN)
        self.assertTrue(response.data["user"]["login_id"].startswith("OIJODO"))

    def test_mismatched_passwords_are_rejected(self):
        response = self.client.post(
            "/api/auth/signup/",
            {
                "company_name": "Odoo India",
                "name": "John Doe",
                "email": "john@odoo.test",
                "password": "Str0ngPass!2026",
                "confirm_password": "different",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("confirm_password", response.data)

    def test_single_word_name_is_rejected(self):
        """The login ID needs both names, so one is not enough."""
        response = self.client.post(
            "/api/auth/signup/",
            {
                "company_name": "Odoo India",
                "name": "Cher",
                "email": "cher@odoo.test",
                "password": "Str0ngPass!2026",
                "confirm_password": "Str0ngPass!2026",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)
