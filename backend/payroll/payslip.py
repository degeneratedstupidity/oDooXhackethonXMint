"""Payslip computation.

The specification ties pay to attendance: the payable days for a month come from the
attendance records, and any unpaid leave or day with no attendance at all reduces them.

Nothing here is stored. A payslip is derived from attendance, approved leave and the
salary structure at the moment it is requested, so it can never disagree with the records
it is drawn from.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from attendance.models import Attendance
from timeoff.models import TimeOffRequest, TimeOffStatus


@dataclass
class Payslip:
    year: int
    month: int
    working_days: int
    days_present: int
    paid_leave_days: int
    unpaid_leave_days: int
    unaccounted_days: int
    payable_days: int
    gross_pay: Decimal
    per_day_rate: Decimal
    deductions: dict
    net_pay: Decimal
    components: list


def _working_days(year, month, days_per_week):
    """Working days in the month, based on the employee's configured week.

    A five-day week means Monday to Friday; a six-day week adds Saturday. Public holidays
    are not modelled — the specification does not define a company calendar — so they are
    counted as working days.
    """
    total = monthrange(year, month)[1]
    # weekday() is 0 for Monday, so a five-day week keeps 0-4 and a six-day week keeps 0-5.
    return sum(
        1
        for day in range(1, total + 1)
        if date(year, month, day).weekday() < days_per_week
    )


def _days_in_month(request, year, month):
    """How many days of a leave request fall inside the given month."""
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    start = max(request.start_date, first)
    end = min(request.end_date, last)
    if start > end:
        return 0
    return (end - start).days + 1


def compute_payslip(structure, year, month):
    """Build the payslip for one employee and month."""
    user = structure.user
    working_days = _working_days(year, month, structure.working_days_per_week)

    attendance_dates = set(
        Attendance.objects.filter(user=user, date__year=year, date__month=month)
        .values_list("date", flat=True)
    )
    days_present = len(attendance_dates)

    approved = TimeOffRequest.objects.filter(
        user=user,
        status=TimeOffStatus.APPROVED,
        start_date__lte=date(year, month, monthrange(year, month)[1]),
        end_date__gte=date(year, month, 1),
    ).select_related("type")

    paid_leave_days = 0
    unpaid_leave_days = 0
    leave_dates = set()

    for request in approved:
        days = _days_in_month(request, year, month)
        if request.type.is_paid:
            paid_leave_days += days
        else:
            unpaid_leave_days += days

        cursor = max(request.start_date, date(year, month, 1))
        finish = min(request.end_date, date(year, month, monthrange(year, month)[1]))
        while cursor <= finish:
            leave_dates.add(cursor)
            cursor += timedelta(days=1)

    # Working days with neither an attendance record nor approved leave. The specification
    # counts these against pay the same way unpaid leave is counted.
    unaccounted_days = 0
    total_days = monthrange(year, month)[1]
    for day_number in range(1, total_days + 1):
        day = date(year, month, day_number)
        if day.weekday() >= structure.working_days_per_week:
            continue
        if day in attendance_dates or day in leave_dates:
            continue
        # Days before joining, or in the future, are not the employee's absence.
        if day < user.date_of_joining or day > date.today():
            continue
        unaccounted_days += 1

    payable_days = max(0, working_days - unpaid_leave_days - unaccounted_days)

    per_day_rate = (
        (structure.monthly_wage / working_days).quantize(Decimal("0.01"))
        if working_days
        else Decimal("0")
    )
    gross_pay = (per_day_rate * payable_days).quantize(Decimal("0.01"))

    # Statutory deductions scale with what is actually earned, not the full wage.
    earned_ratio = (
        Decimal(payable_days) / Decimal(working_days) if working_days else Decimal("0")
    )
    pf = (structure.pf_employee_amount * earned_ratio).quantize(Decimal("0.01"))
    professional_tax = structure.professional_tax if gross_pay > 0 else Decimal("0")

    deductions = {
        "provident_fund": pf,
        "professional_tax": professional_tax,
        "total": (pf + professional_tax).quantize(Decimal("0.01")),
    }

    return Payslip(
        year=year,
        month=month,
        working_days=working_days,
        days_present=days_present,
        paid_leave_days=paid_leave_days,
        unpaid_leave_days=unpaid_leave_days,
        unaccounted_days=unaccounted_days,
        payable_days=payable_days,
        gross_pay=gross_pay,
        per_day_rate=per_day_rate,
        deductions=deductions,
        net_pay=(gross_pay - deductions["total"]).quantize(Decimal("0.01")),
        components=[
            {
                "code": component.code,
                "label": component.get_code_display(),
                "full_amount": component.amount,
                "earned": (component.amount * earned_ratio).quantize(Decimal("0.01")),
            }
            for component in structure.components.all()
        ],
    )
