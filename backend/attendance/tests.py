from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from accounts.seed import create_salary_structure
from accounts.tests import make_company, make_user

from .models import Attendance


class CheckInOutTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.employee = make_user(self.company, "Priya", "Nair", role=Role.EMPLOYEE)
        self.client = APIClient()
        self.client.force_authenticate(user=self.employee)

    def test_check_in_opens_a_record(self):
        response = self.client.post("/api/attendance/check_in/")
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["check_out"])

    def test_checking_in_twice_is_refused(self):
        self.client.post("/api/attendance/check_in/")
        response = self.client.post("/api/attendance/check_in/")
        self.assertEqual(response.status_code, 400)

    def test_check_out_closes_the_record(self):
        self.client.post("/api/attendance/check_in/")
        response = self.client.post("/api/attendance/check_out/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["check_out"])

    def test_check_out_without_check_in_is_refused(self):
        response = self.client.post("/api/attendance/check_out/")
        self.assertEqual(response.status_code, 400)

    def test_checking_out_twice_is_refused(self):
        self.client.post("/api/attendance/check_in/")
        self.client.post("/api/attendance/check_out/")
        response = self.client.post("/api/attendance/check_out/")
        self.assertEqual(response.status_code, 400)


class WorkHoursTests(TestCase):
    """Worked time is time on the premises less the employee's break."""

    def setUp(self):
        self.company = make_company()
        self.employee = make_user(self.company, "Priya", "Nair", role=Role.EMPLOYEE)
        self.structure = create_salary_structure(self.company, self.employee)

    def record(self, hours):
        start = timezone.now() - timedelta(hours=hours)
        return Attendance.objects.create(
            company=self.company,
            user=self.employee,
            date=timezone.localdate(),
            check_in=start,
            check_out=start + timedelta(hours=hours),
        )

    def test_attended_hours_are_the_raw_time_on_the_premises(self):
        self.assertEqual(self.record(9).attended_hours, 9.0)

    def test_the_break_is_deducted_from_worked_hours(self):
        # Nine hours in the building, an hour of it on break.
        self.assertEqual(self.record(9).work_hours, 8.0)

    def test_a_configured_break_is_respected(self):
        self.structure.break_time_hours = Decimal("0.5")
        self.structure.save(update_fields=["break_time_hours"])
        self.assertEqual(self.record(9).work_hours, 8.5)

    def test_a_long_day_records_extra_hours_after_the_break(self):
        # Eleven hours attended, one on break, so ten worked against an eight-hour day.
        self.assertEqual(self.record(11).extra_hours, 2.0)

    def test_a_short_day_records_no_negative_overtime(self):
        self.assertEqual(self.record(6).extra_hours, 0.0)

    def test_a_day_shorter_than_the_break_does_not_go_negative(self):
        self.assertEqual(self.record(0.5).work_hours, 0.0)

    def test_an_open_record_has_no_hours_yet(self):
        record = Attendance.objects.create(
            company=self.company,
            user=self.employee,
            date=timezone.localdate(),
            check_in=timezone.now(),
        )
        self.assertEqual(record.work_hours, 0.0)

    def test_an_employee_without_a_salary_structure_falls_back_to_a_default_break(self):
        other = make_user(self.company, "Karthik", "Iyer", role=Role.EMPLOYEE)
        start = timezone.now() - timedelta(hours=9)
        record = Attendance.objects.create(
            company=self.company,
            user=other,
            date=timezone.localdate(),
            check_in=start,
            check_out=start + timedelta(hours=9),
        )
        self.assertEqual(record.work_hours, 8.0)


class AttendanceVisibilityTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.hr = make_user(self.company, "Rahul", "Verma", role=Role.HR_OFFICER)
        self.employee = make_user(self.company, "Priya", "Nair", role=Role.EMPLOYEE)
        for user in (self.hr, self.employee):
            Attendance.objects.create(
                company=self.company,
                user=user,
                date=timezone.localdate(),
                check_in=timezone.now(),
            )
        self.client = APIClient()

    def test_an_employee_sees_only_their_own_attendance(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.get("/api/attendance/")
        self.assertEqual(len(response.data), 1)

    def test_an_hr_officer_sees_everyones_attendance(self):
        self.client.force_authenticate(user=self.hr)
        response = self.client.get("/api/attendance/")
        self.assertEqual(len(response.data), 2)
