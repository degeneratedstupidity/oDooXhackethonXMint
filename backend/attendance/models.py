from datetime import timedelta

from django.db import models

from accounts.models import TenantScopedModel, User

# Used to derive extra hours. A full-time day in the wireframes is 09:00-19:00 with an
# hour of break, so eight hours is the expected working day.
STANDARD_WORKING_HOURS = 8


class Attendance(TenantScopedModel):
    """One working day for one employee.

    A row is created on check-in and closed on check-out, so an open row (check_out is
    null) means the employee is currently in the office.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="attendances")
    date = models.DateField()
    check_in = models.DateTimeField()
    check_out = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "-check_in"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="one_attendance_row_per_employee_per_day"
            )
        ]

    def __str__(self):
        return f"{self.user.login_id} on {self.date}"

    @property
    def worked(self) -> timedelta:
        if not self.check_out:
            return timedelta()
        return self.check_out - self.check_in

    @property
    def work_hours(self) -> float:
        return round(self.worked.total_seconds() / 3600, 2)

    @property
    def extra_hours(self) -> float:
        """Hours beyond a standard day. Never negative — a short day is not negative overtime."""
        return round(max(0.0, self.work_hours - STANDARD_WORKING_HOURS), 2)
