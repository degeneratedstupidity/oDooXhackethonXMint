from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role
from accounts.tests import make_company, make_user

from .models import TimeOffRequest, TimeOffStatus, TimeOffType


class TimeOffValidationTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.employee = make_user(self.company, "Priya", "Nair", role=Role.EMPLOYEE)
        self.paid = TimeOffType.objects.get(company=self.company, name="Paid Time Off")
        self.sick = TimeOffType.objects.get(company=self.company, name="Sick Leave")
        self.client = APIClient()
        self.client.force_authenticate(user=self.employee)

    def request_payload(self, start, end, leave_type=None):
        return {
            "type": (leave_type or self.paid).id,
            "start_date": start,
            "end_date": end,
        }

    def test_a_valid_request_is_created_awaiting_approval(self):
        response = self.client.post(
            "/api/time-off/", self.request_payload("2026-09-01", "2026-09-03"), format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], TimeOffStatus.TO_APPROVE)
        self.assertEqual(response.data["days"], 3)

    def test_end_before_start_is_rejected(self):
        response = self.client.post(
            "/api/time-off/", self.request_payload("2026-09-10", "2026-09-01"), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("end_date", response.data)

    def test_overlapping_request_is_rejected(self):
        self.client.post(
            "/api/time-off/", self.request_payload("2026-09-01", "2026-09-05"), format="json"
        )
        response = self.client.post(
            "/api/time-off/", self.request_payload("2026-09-04", "2026-09-08"), format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_a_refused_request_does_not_block_the_same_dates(self):
        """Only pending or approved requests hold dates."""
        first = self.client.post(
            "/api/time-off/", self.request_payload("2026-09-01", "2026-09-05"), format="json"
        )
        TimeOffRequest.objects.filter(pk=first.data["id"]).update(
            status=TimeOffStatus.REFUSED
        )
        response = self.client.post(
            "/api/time-off/", self.request_payload("2026-09-01", "2026-09-05"), format="json"
        )
        self.assertEqual(response.status_code, 201)

    def test_sick_leave_requires_a_document(self):
        response = self.client.post(
            "/api/time-off/",
            self.request_payload("2026-09-01", "2026-09-02", self.sick),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("attachment", response.data)

    def test_a_single_day_request_counts_as_one_day(self):
        response = self.client.post(
            "/api/time-off/", self.request_payload("2026-09-01", "2026-09-01"), format="json"
        )
        self.assertEqual(response.data["days"], 1)


class TimeOffApprovalTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.hr = make_user(self.company, "Rahul", "Verma", role=Role.HR_OFFICER)
        self.employee = make_user(self.company, "Priya", "Nair", role=Role.EMPLOYEE)
        self.paid = TimeOffType.objects.get(company=self.company, name="Paid Time Off")
        self.request = TimeOffRequest.objects.create(
            company=self.company,
            user=self.employee,
            type=self.paid,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 3),
        )
        self.client = APIClient()

    def test_hr_officer_can_approve(self):
        self.client.force_authenticate(user=self.hr)
        response = self.client.post(f"/api/time-off/{self.request.id}/approve/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], TimeOffStatus.APPROVED)

    def test_employee_cannot_approve_their_own_request(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.post(f"/api/time-off/{self.request.id}/approve/")
        self.assertEqual(response.status_code, 403)

    def test_a_decided_request_cannot_be_decided_again(self):
        self.client.force_authenticate(user=self.hr)
        self.client.post(f"/api/time-off/{self.request.id}/approve/")
        response = self.client.post(f"/api/time-off/{self.request.id}/refuse/")
        self.assertEqual(response.status_code, 400)

    def test_employees_see_only_their_own_requests(self):
        other = make_user(self.company, "Karthik", "Iyer", role=Role.EMPLOYEE)
        TimeOffRequest.objects.create(
            company=self.company,
            user=other,
            type=self.paid,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
        )
        self.client.force_authenticate(user=self.employee)
        response = self.client.get("/api/time-off/")
        self.assertEqual(len(response.data), 1)

    def test_hr_officer_sees_every_request(self):
        self.client.force_authenticate(user=self.hr)
        response = self.client.get("/api/time-off/")
        self.assertEqual(len(response.data), 1)


class BalanceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.employee = make_user(self.company, "Priya", "Nair", role=Role.EMPLOYEE)
        self.client = APIClient()
        self.client.force_authenticate(user=self.employee)

    def test_approved_leave_is_deducted_from_the_allowance(self):
        paid = TimeOffType.objects.get(company=self.company, name="Paid Time Off")
        TimeOffRequest.objects.create(
            company=self.company,
            user=self.employee,
            type=paid,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 3),
            status=TimeOffStatus.APPROVED,
        )
        response = self.client.get("/api/time-off/balances/")
        paid_balance = next(b for b in response.data if b["name"] == "Paid Time Off")
        self.assertEqual(paid_balance["used"], 3)
        self.assertEqual(paid_balance["available"], 21.0)

    def test_an_uncapped_type_reports_no_balance(self):
        response = self.client.get("/api/time-off/balances/")
        unpaid = next(b for b in response.data if b["name"] == "Unpaid Leave")
        self.assertIsNone(unpaid["available"])

    def test_pending_leave_is_not_yet_deducted(self):
        paid = TimeOffType.objects.get(company=self.company, name="Paid Time Off")
        TimeOffRequest.objects.create(
            company=self.company,
            user=self.employee,
            type=paid,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 3),
            status=TimeOffStatus.TO_APPROVE,
        )
        response = self.client.get("/api/time-off/balances/")
        paid_balance = next(b for b in response.data if b["name"] == "Paid Time Off")
        self.assertEqual(paid_balance["used"], 0)
