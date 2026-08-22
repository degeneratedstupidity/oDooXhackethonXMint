# Dayflow — Human Resource Management System

An HRMS built for the Odoo Hackathon. Multi-tenant: each company signs up, gets its own isolated data, and
manages its employees, attendance, time off, and payroll.

## Stack

- **Backend:** Django + Django REST Framework
- **Frontend:** Next.js (App Router, TypeScript) + Tailwind
- **Database:** PostgreSQL
- **Runtime:** Docker Compose (all services containerised)

## Getting started

Requires Docker Desktop running.

```bash
./setup.sh                  # generates .env with fresh secrets
docker compose up --build   # migrations run automatically on start
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api

To explore with realistic data — seven people across the three roles, a month of
attendance and time off in every state:

```bash
docker compose exec backend python manage.py seed_demo
```

It prints a login for each person; the password for all of them is `Demo@2026`. Sign in as
the administrator to see everything, including the salary and payslip views.

`setup.sh` exists because the encryption key must be a valid 32-byte Fernet key — copying
`.env.example` by hand and leaving the placeholder in place would fail at the first write
of a bank detail.

## Tests

```bash
docker compose exec backend python manage.py test
```

71 tests covering login ID generation, the salary computation rules, payslip derivation
from attendance, time off validation and approval, attendance hours, role permissions, and
the two security foundations. The row-level security tests run against the real policies —
the test database is built by the same migrations and Django connects as the same
non-superuser role — so they fail if tenant isolation ever regresses.

## Features

- **Multi-tenant companies** — sign-up creates a company and its first Admin. Employees are created by
  Admin/HR, not self-registered.
- **Auto-generated Login IDs** — format `[company code][name initials][join year][sequence]`,
  e.g. `OIJODO20220001`, with a per-company, per-year sequence.
- **Roles** — Admin, HR Officer, Employee, each with a different view of the system.
- **Attendance** — check in/out, work hours and extra hours, day and month views.
- **Time off** — request, approve/reject, per-type balances (paid, sick, unpaid).
- **Payroll** — salary structure with components auto-computed from the defined wage, PF and tax config.
  Visible to Admin only.

## Security

- Passwords hashed with Django's default hasher; first-login passwords are system-generated.
- **Row-Level Security** in PostgreSQL scopes every company-owned table by tenant, enforced at the database
  level rather than only in application code.
- **Field-level encryption** on bank and identity details (account number, IFSC, PAN, UAN).
- Role and ownership checks in DRF permissions and serializers on every read and write path.
- All input validated server-side; the client is never trusted.
- Sign-in is rate limited, since login IDs follow a published format and would otherwise be
  enumerable and guessable. Sign-up and password changes are bounded too.
- Employees are deactivated, never deleted, so attendance and payroll history survives the
  person leaving.

## Project layout

```
backend/     Django project — API, models, migrations
frontend/    Next.js app
```

## Design decisions

Where the specification left room for interpretation, here is what we chose and why.

**Fixed Allowance follows the stated formula, not the illustrated figure.** The specification gives the
rule `Fixed allowance = wage - total of all the components`, but the accompanying mockup shows ₹2,918.00
against a ₹50,000 wage. Those disagree: the mockup's own components sum to ₹48,750, leaving ₹1,250
unaccounted for, whereas the stated rule yields ₹4,168. We implemented the rule, because the specification
separately requires that components never exceed the wage, and only the rule guarantees the components sum
to exactly the wage at every wage value. On the worked example, every other component matches the mockup
precisely (Basic ₹25,000, HRA ₹12,500, Standard ₹4,167, Bonus and LTA ₹2,082.50).

**Row-level security covers data tables, not the user table.** Authentication has to resolve a login ID
before the user's company is known, so a policy on the user table would make every login fail. That table
is scoped in the application layer instead; everything else is enforced by Postgres.

**Salary is Admin-only; HR Officers are not.** The specification marks the Salary Info tab as
administrator-only, so HR Officers can manage people, attendance and leave, but the salary endpoints
return 403 for them.

**Leave is counted in calendar days.** Requests count both end dates inclusively, so a Friday-to-Monday
request is four days against the allowance.

**Public holidays belong to the company, not the system.** The specification's calendar shows an Indian
holiday list, so that set is seeded for a new company, but companies observe different holidays and operate
in different regions — the model is per company and editable rather than global. A holiday is excluded from
working days and never counted as an absence, so nobody loses a day's pay for a day nobody was expected to
work.
