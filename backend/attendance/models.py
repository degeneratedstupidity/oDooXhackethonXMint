from datetime import timedelta
from decimal import Decimal

from django.db import models

from accounts.models import TenantScopedModel, User

# Used only when an employee has no salary structure to read a schedule from.
DEFAULT_WORKING_HOURS = Decimal("8")
DEFAULT_BREAK_HOURS = Decimal("1")


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
    def break_hours(self) -> Decimal:
        """The employee's configured break, which is unpaid time on the premises."""
        structure = getattr(self.user, "salary", None)
        if structure and structure.break_time_hours is not None:
            return Decimal(str(structure.break_time_hours))
        return DEFAULT_BREAK_HOURS

    @property
    def expected_hours(self) -> Decimal:
        """The working day this employee is measured against."""
        return DEFAULT_WORKING_HOURS

    @property
    def worked(self) -> timedelta:
        """Time between check-in and check-out, before the break is taken off."""
        if not self.check_out:
            return timedelta()
        return self.check_out - self.check_in

    @property
    def attended_hours(self) -> float:
        """Time on the premises, break included."""
        return round(self.worked.total_seconds() / 3600, 2)

    @property
    def work_hours(self) -> float:
        """Time actually worked: attendance less the employee's break.

        The specification asks for attendance shown against working time including
        breaks, so an employee in from 10:00 to 19:00 with an hour's break has worked
        eight hours, not nine.
        """
        if not self.check_out:
            return 0.0
        worked = Decimal(str(self.attended_hours)) - self.break_hours
        return round(float(max(Decimal("0"), worked)), 2)

    @property
    def extra_hours(self) -> float:
        """Hours beyond the expected day. Never negative — a short day is not overtime."""
        return round(max(0.0, self.work_hours - float(self.expected_hours)), 2)
