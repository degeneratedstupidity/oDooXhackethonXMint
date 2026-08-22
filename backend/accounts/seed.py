"""Defaults created for each new company so the product is usable immediately."""

from datetime import date

from timeoff.models import PublicHoliday, TimeOffType

# Matches the wireframes: paid and sick leave carry an annual allowance, unpaid leave is
# uncapped but does not count as a payable day.
DEFAULT_TIME_OFF_TYPES = [
    {"name": "Paid Time Off", "is_paid": True, "default_days_per_year": 24},
    {"name": "Sick Leave", "is_paid": True, "default_days_per_year": 7, "requires_attachment": True},
    {"name": "Unpaid Leave", "is_paid": False, "default_days_per_year": 0},
]


# The list shown in the specification's calendar. Seeded as a starting point — a company
# edits its own set from here.
DEFAULT_PUBLIC_HOLIDAYS_2026 = [
    ("Kite Festival", date(2026, 1, 14)),
    ("Republic Day", date(2026, 1, 26)),
    ("Dhuleti", date(2026, 3, 4)),
    ("Independence Day", date(2026, 8, 15)),
    ("Rakhi", date(2026, 8, 28)),
    ("Gandhi Jayanti", date(2026, 10, 2)),
    ("Diwali", date(2026, 11, 8)),
    ("New Year", date(2026, 11, 10)),
    ("Bhai Duj", date(2026, 11, 11)),
]


def seed_default_time_off_types(company):
    TimeOffType.objects.bulk_create(
        [TimeOffType(company=company, **values) for values in DEFAULT_TIME_OFF_TYPES]
    )
    PublicHoliday.objects.bulk_create(
        [
            PublicHoliday(company=company, name=name, date=day)
            for name, day in DEFAULT_PUBLIC_HOLIDAYS_2026
        ]
    )


def create_salary_structure(company, user):
    """Every employee gets a structure with the standard components, on a zero wage
    until an administrator sets one."""
    from payroll.models import SalaryStructure

    structure = SalaryStructure.objects.create(company=company, user=user)
    structure.apply_default_components()
    return structure
