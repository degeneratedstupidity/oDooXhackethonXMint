from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from accounts.seed import create_salary_structure
from accounts.tests import make_company, make_user
from attendance.models import Attendance
from timeoff.models import PublicHoliday, TimeOffRequest, TimeOffStatus, TimeOffType

from .models import ComponentCode, SalaryStructure
from .payslip import compute_payslip


class SalaryComputationTests(TestCase):
    """The worked example from the specification: a 50,000 wage."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.structure = create_salary_structure(self.company, self.user)
        self.structure.monthly_wage = Decimal("50000")
        self.structure.save()
        self.structure.recompute()

    def amount(self, code):
        return self.structure.components.get(code=code).amount

    def test_basic_is_half_the_wage(self):
        self.assertEqual(self.amount(ComponentCode.BASIC), Decimal("25000.00"))

    def test_hra_is_half_of_basic(self):
        self.assertEqual(self.amount(ComponentCode.HRA), Decimal("12500.00"))

    def test_percentage_components_follow_basic(self):
        self.assertEqual(self.amount(ComponentCode.PERFORMANCE_BONUS), Decimal("2082.50"))
        self.assertEqual(self.amount(ComponentCode.LTA), Decimal("2082.50"))

    def test_components_sum_to_exactly_the_wage(self):
        total = sum(component.amount for component in self.structure.components.all())
        self.assertEqual(total, Decimal("50000.00"))

    def test_fixed_allowance_absorbs_the_remainder(self):
        """The specification's rule: fixed allowance = wage - every other component."""
        others = sum(
            component.amount
            for component in self.structure.components.exclude(code=ComponentCode.FIXED)
        )
        self.assertEqual(
            self.amount(ComponentCode.FIXED), Decimal("50000.00") - others
        )

    def test_changing_the_wage_recomputes_every_component(self):
        self.structure.monthly_wage = Decimal("80000")
        self.structure.save()
        self.structure.recompute()

        self.assertEqual(self.amount(ComponentCode.BASIC), Decimal("40000.00"))
        self.assertEqual(self.amount(ComponentCode.HRA), Decimal("20000.00"))
        total = sum(component.amount for component in self.structure.components.all())
        self.assertEqual(total, Decimal("80000.00"))

    def test_provident_fund_is_calculated_on_basic_not_wage(self):
        # 12% of 25,000 basic, not of the 50,000 wage.
        self.assertEqual(self.structure.pf_employee_amount, Decimal("3000.00"))

    def test_a_zero_wage_leaves_no_negative_components(self):
        self.structure.monthly_wage = Decimal("0")
        self.structure.save()
        self.structure.recompute()
        for component in self.structure.components.all():
            self.assertGreaterEqual(component.amount, Decimal("0"), component.code)


class SalaryApiTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, "Asha", "Menon", role=Role.ADMIN)
        self.hr = make_user(self.company, "Rahul", "Verma", role=Role.HR_OFFICER)
        self.employee = make_user(self.company, "Priya", "Nair", role=Role.EMPLOYEE)
        for user in (self.admin, self.hr, self.employee):
            create_salary_structure(self.company, user)
        self.client = APIClient()

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_admin_can_read_salary(self):
        self.authenticate(self.admin)
        self.assertEqual(self.client.get("/api/salary/").status_code, 200)

    def test_hr_officer_cannot_read_salary(self):
        """Salary is administrator-only, per the specification."""
        self.authenticate(self.hr)
        self.assertEqual(self.client.get("/api/salary/").status_code, 403)

    def test_employee_cannot_read_salary(self):
        self.authenticate(self.employee)
        self.assertEqual(self.client.get("/api/salary/").status_code, 403)

    def test_wage_below_committed_components_is_rejected(self):
        self.authenticate(self.admin)
        structure = SalaryStructure.objects.get(user=self.admin)
        structure.monthly_wage = Decimal("50000")
        structure.save()
        structure.recompute()

        # Standard Allowance alone is a fixed 4,167, so a 3,000 wage cannot work.
        response = self.client.patch(
            f"/api/salary/{structure.id}/", {"monthly_wage": "3000"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_negative_wage_is_rejected(self):
        self.authenticate(self.admin)
        structure = SalaryStructure.objects.get(user=self.admin)
        response = self.client.patch(
            f"/api/salary/{structure.id}/", {"monthly_wage": "-100"}, format="json"
        )
        self.assertEqual(response.status_code, 400)


class PayslipTests(TestCase):
    """Attendance drives pay, as the specification requires."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company, joining=date(2026, 1, 1))
        self.structure = create_salary_structure(self.company, self.user)
        self.structure.monthly_wage = Decimal("50000")
        self.structure.save()
        self.structure.recompute()

    def test_full_attendance_gives_full_payable_days(self):
        """Every working day in June 2026 attended."""
        for day in range(1, 31):
            current = date(2026, 6, day)
            if current.weekday() < 5:
                Attendance.objects.create(
                    company=self.company,
                    user=self.user,
                    date=current,
                    check_in=timezone.make_aware(
                        timezone.datetime(2026, 6, day, 9, 0)
                    ),
                    check_out=timezone.make_aware(
                        timezone.datetime(2026, 6, day, 18, 0)
                    ),
                )

        payslip = compute_payslip(self.structure, 2026, 6)
        self.assertEqual(payslip.payable_days, payslip.working_days)
        self.assertEqual(payslip.unaccounted_days, 0)

    def test_unpaid_leave_reduces_payable_days(self):
        unpaid = TimeOffType.objects.get(company=self.company, name="Unpaid Leave")
        TimeOffRequest.objects.create(
            company=self.company,
            user=self.user,
            type=unpaid,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            status=TimeOffStatus.APPROVED,
        )
        payslip = compute_payslip(self.structure, 2026, 6)
        self.assertEqual(payslip.unpaid_leave_days, 3)
        self.assertLess(payslip.payable_days, payslip.working_days)

    def test_paid_leave_does_not_reduce_payable_days(self):
        paid = TimeOffType.objects.get(company=self.company, name="Paid Time Off")
        TimeOffRequest.objects.create(
            company=self.company,
            user=self.user,
            type=paid,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            status=TimeOffStatus.APPROVED,
        )
        payslip = compute_payslip(self.structure, 2026, 6)
        self.assertEqual(payslip.paid_leave_days, 3)
        self.assertEqual(payslip.unpaid_leave_days, 0)

    def test_days_before_joining_are_not_counted_as_absence(self):
        late_joiner = make_user(
            self.company, "Late", "Joiner", role=Role.EMPLOYEE, joining=date(2026, 6, 20)
        )
        structure = create_salary_structure(self.company, late_joiner)
        payslip = compute_payslip(structure, 2026, 6)
        # Only working days from the 20th onward can count against them.
        self.assertLess(payslip.unaccounted_days, payslip.working_days)

    def test_payable_days_never_go_negative(self):
        unpaid = TimeOffType.objects.get(company=self.company, name="Unpaid Leave")
        TimeOffRequest.objects.create(
            company=self.company,
            user=self.user,
            type=unpaid,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            status=TimeOffStatus.APPROVED,
        )
        payslip = compute_payslip(self.structure, 2026, 6)
        self.assertGreaterEqual(payslip.payable_days, 0)


class PublicHolidayPayrollTests(TestCase):
    """A holiday is not a working day, and not an absence."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company, joining=date(2026, 1, 1))
        self.structure = create_salary_structure(self.company, self.user)
        self.structure.monthly_wage = Decimal("50000")
        self.structure.save()
        self.structure.recompute()

    def test_a_holiday_reduces_the_working_day_count(self):
        before = compute_payslip(self.structure, 2026, 7).working_days
        # 1 July 2026 is a Wednesday.
        PublicHoliday.objects.create(
            company=self.company, name="Test Holiday", date=date(2026, 7, 1)
        )
        after = compute_payslip(self.structure, 2026, 7).working_days
        self.assertEqual(after, before - 1)

    def test_a_holiday_is_not_counted_as_an_absence(self):
        PublicHoliday.objects.create(
            company=self.company, name="Test Holiday", date=date(2026, 7, 1)
        )
        payslip = compute_payslip(self.structure, 2026, 7)
        # With no attendance at all, every other working day is unaccounted, but the
        # holiday must not be among them.
        self.assertEqual(payslip.unaccounted_days, payslip.working_days)

    def test_a_weekend_holiday_changes_nothing(self):
        before = compute_payslip(self.structure, 2026, 7).working_days
        # 4 July 2026 is a Saturday, already outside a five-day week.
        PublicHoliday.objects.create(
            company=self.company, name="Weekend Holiday", date=date(2026, 7, 4)
        )
        self.assertEqual(compute_payslip(self.structure, 2026, 7).working_days, before)
