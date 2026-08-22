"""Defaults created for each new company so the product is usable immediately."""

from timeoff.models import TimeOffType

# Matches the wireframes: paid and sick leave carry an annual allowance, unpaid leave is
# uncapped but does not count as a payable day.
DEFAULT_TIME_OFF_TYPES = [
    {"name": "Paid Time Off", "is_paid": True, "default_days_per_year": 24},
    {"name": "Sick Leave", "is_paid": True, "default_days_per_year": 7, "requires_attachment": True},
    {"name": "Unpaid Leave", "is_paid": False, "default_days_per_year": 0},
]


def seed_default_time_off_types(company):
    TimeOffType.objects.bulk_create(
        [TimeOffType(company=company, **values) for values in DEFAULT_TIME_OFF_TYPES]
    )
