"""Populate a demo company so the product can be shown with realistic data.

Creates one company with an admin, an HR officer and several employees, then backfills
a month of attendance and a spread of time off requests.

    docker compose exec backend python manage.py seed_demo
"""

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import BankDetail, Company, EmployeeProfile, Role, User
from accounts.seed import create_salary_structure, seed_default_time_off_types
from accounts.tenancy import set_current_company
from attendance.models import Attendance
from timeoff.models import TimeOffRequest, TimeOffStatus, TimeOffType

PASSWORD = "Demo@2026"

PEOPLE = [
    # first, last, role, position, department, monthly wage
    ("Asha", "Menon", Role.ADMIN, "Chief People Officer", "Leadership", 120000),
    ("Rahul", "Verma", Role.HR_OFFICER, "HR Officer", "People", 65000),
    ("Priya", "Nair", Role.EMPLOYEE, "Senior Engineer", "Engineering", 95000),
    ("Karthik", "Iyer", Role.EMPLOYEE, "Engineer", "Engineering", 70000),
    ("Sneha", "Reddy", Role.EMPLOYEE, "Product Designer", "Design", 78000),
    ("Arjun", "Das", Role.EMPLOYEE, "Data Analyst", "Analytics", 62000),
    ("Meera", "Pillai", Role.EMPLOYEE, "Account Manager", "Sales", 58000),
]

LOCATIONS = ["Bengaluru", "Mumbai", "Pune", "Remote"]


class Command(BaseCommand):
    help = "Create a demo company with employees, attendance and time off."

    def add_arguments(self, parser):
        parser.add_argument("--company", default="Odoo India")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete an existing company of the same name first.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        name = options["company"]

        if options["reset"]:
            self._delete_company(name)
        if Company.objects.filter(name=name).exists():
            self.stdout.write(
                self.style.WARNING(f"{name} already exists. Re-run with --reset to replace it.")
            )
            return

        company = Company.objects.create(name=name, code=Company.derive_code(name))
        # Every table below is behind row-level security, so the scope has to be set
        # before anything is inserted.
        set_current_company(company.id)
        seed_default_time_off_types(company)

        users = []
        for index, (first, last, role, position, department, wage) in enumerate(PEOPLE):
            joining = date(2022 + index % 4, 1 + index % 12, 1 + index % 27)
            user = User.objects.create_user(
                login_id=User.generate_login_id(company, first, last, joining.year),
                email=f"{first.lower()}.{last.lower()}@{company.code.lower()}.example",
                password=PASSWORD,
                company=company,
                first_name=first,
                last_name=last,
                phone=f"98{random.randint(10000000, 99999999)}",
                role=role,
                date_of_joining=joining,
            )
            EmployeeProfile.objects.create(
                company=company,
                user=user,
                job_position=position,
                department=department,
                location=random.choice(LOCATIONS),
                nationality="Indian",
                personal_email=f"{first.lower()}@personal.example",
                about=f"{position} on the {department} team.",
            )
            BankDetail.objects.create(
                company=company,
                user=user,
                bank_name=random.choice(["HDFC Bank", "ICICI Bank", "State Bank of India"]),
                account_number=str(random.randint(10**11, 10**12 - 1)),
                ifsc_code=f"HDFC000{random.randint(1000, 9999)}",
                pan_number=f"ABCPE{random.randint(1000, 9999)}K",
            )
            structure = create_salary_structure(company, user)
            structure.monthly_wage = Decimal(wage)
            structure.save(update_fields=["monthly_wage"])
            structure.recompute()
            users.append(user)

        # Everyone reports to the admin, except the admin.
        admin = users[0]
        EmployeeProfile.objects.filter(company=company).exclude(user=admin).update(manager=admin)

        self._seed_attendance(company, users)
        self._seed_time_off(company, users)

        self.stdout.write(self.style.SUCCESS(f"\nCreated {name} with {len(users)} people.\n"))
        self.stdout.write("Sign in with any of these — password for all is " + PASSWORD + "\n")
        for user in users:
            self.stdout.write(f"  {user.login_id}   {user.get_role_display():<12} {user.full_name}")

    def _delete_company(self, name):
        """Tear down a demo company completely.

        Two things make this more than a one-line delete. The company scope has to be set
        first, because Django's cascade collector queries the related tables and row-level
        security hides company-scoped rows from an unscoped session — the collector would
        miss them and Postgres would refuse the delete on the foreign key. And leave
        requests have to go before their types, which are deliberately PROTECTed so a type
        in use cannot be removed in normal operation.
        """
        existing = Company.objects.filter(name=name).first()
        if not existing:
            return

        set_current_company(existing.id)
        TimeOffRequest.objects.filter(company=existing).delete()
        TimeOffType.objects.filter(company=existing).delete()
        existing.delete()
        set_current_company(None)

    def _seed_attendance(self, company, users):
        """A month of weekday attendance, with some variation in hours and absences."""
        today = timezone.localdate()
        current_timezone = timezone.get_current_timezone()

        for user in users:
            for offset in range(30, -1, -1):
                day = today - timedelta(days=offset)
                if day.weekday() >= 5:
                    continue
                # A believable attendance rate rather than a perfect record.
                if random.random() < 0.12:
                    continue

                start = datetime.combine(
                    day, time(hour=random.choice([9, 9, 10]), minute=random.choice([0, 15, 30]))
                )
                worked = timedelta(hours=random.choice([8, 8, 9, 9, 10]), minutes=random.choice([0, 30]))
                check_in = timezone.make_aware(start, current_timezone)

                # Today's row is left open, so the check-out control has something to do.
                check_out = None if day == today else check_in + worked

                Attendance.objects.create(
                    company=company, user=user, date=day, check_in=check_in, check_out=check_out
                )

    def _seed_time_off(self, company, users):
        """A mix of approved, refused and pending requests so the approval queue is not empty."""
        types = list(TimeOffType.objects.filter(company=company))
        approver = users[0]
        today = timezone.localdate()

        plans = [
            (users[2], types[0], -20, 3, TimeOffStatus.APPROVED),
            (users[3], types[1], -12, 2, TimeOffStatus.APPROVED),
            (users[4], types[0], -5, 1, TimeOffStatus.REFUSED),
            (users[5], types[0], 6, 4, TimeOffStatus.TO_APPROVE),
            (users[6], types[1], 10, 2, TimeOffStatus.TO_APPROVE),
            (users[2], types[2], 20, 3, TimeOffStatus.TO_APPROVE),
        ]

        for user, leave_type, start_offset, length, status in plans:
            start = today + timedelta(days=start_offset)
            reviewed = status != TimeOffStatus.TO_APPROVE
            TimeOffRequest.objects.create(
                company=company,
                user=user,
                type=leave_type,
                start_date=start,
                end_date=start + timedelta(days=length - 1),
                reason=random.choice(
                    ["Family commitment", "Travel", "Medical", "Personal", "Wedding"]
                ),
                status=status,
                reviewed_by=approver if reviewed else None,
                reviewed_at=timezone.now() if reviewed else None,
            )
