from django.db import models

from accounts.models import TenantScopedModel, User


class TimeOffStatus(models.TextChoices):
    TO_APPROVE = "to_approve", "To Approve"
    APPROVED = "approved", "Approved"
    REFUSED = "refused", "Refused"


class TimeOffType(TenantScopedModel):
    """A category of leave. Seeded per company: paid, sick and unpaid.

    `is_paid` is what payroll reads: unpaid leave reduces payable days, paid leave does not.
    """

    name = models.CharField(max_length=60)
    is_paid = models.BooleanField(default=True)
    # Days granted per employee per year. Unpaid leave is uncapped.
    default_days_per_year = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    requires_attachment = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TimeOffRequest(TenantScopedModel):
    """One leave request, from submission through approval or refusal."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="time_off_requests")
    type = models.ForeignKey(TimeOffType, on_delete=models.PROTECT, related_name="requests")
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    attachment = models.FileField(upload_to="time-off/", blank=True, null=True)

    status = models.CharField(
        max_length=12, choices=TimeOffStatus.choices, default=TimeOffStatus.TO_APPROVE
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_requests"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.user.login_id} {self.start_date}–{self.end_date}"

    @property
    def days(self) -> int:
        """Inclusive of both end dates, matching how leave is counted on a calendar."""
        return (self.end_date - self.start_date).days + 1


class PublicHoliday(TenantScopedModel):
    """A company holiday. Nobody is expected at work, and nobody loses pay for it.

    Held per company rather than globally: the specification's calendar shows an Indian
    holiday list, but companies observe different sets and operate in different regions.
    """

    name = models.CharField(max_length=120)
    date = models.DateField()

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "date"], name="one_holiday_per_company_per_date"
            )
        ]

    def __str__(self):
        return f"{self.name} on {self.date}"
