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

96 tests covering:
- Login ID generation and sequencing (no duplicates across concurrent creation)
- Salary computation rules, including the specification's worked example (₹50,000 wage)
- Payslip derivation from attendance with dynamic day counts
- Time off validation, overlap detection, approval workflow
- Attendance hour calculation with configurable breaks
- Work hours deductions for leave and public holidays
- Role-based access control (Admin, HR Officer, Employee)
- Private and bank details withheld from colleagues, returned to self, Admin and HR
- Deactivation and reactivation of employees
- Row-level security at the database level (proven against real Postgres policies)
- Field-level encryption at rest (verified by reading raw database columns)
- Login rate limiting
- File URL resolution through proxies

The row-level security tests run against the real policies — the test database is built by
the same migrations and Django connects as the same non-superuser role — so they fail if
tenant isolation ever regresses. Encryption tests read the raw database column to confirm
ciphertext is stored, not plaintext.

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
- Private information (date of birth, home address, personal email) and bank details are
  readable only by the employee themselves, an Admin, or an HR Officer. A colleague opening
  the profile gets a response with those fields absent, not merely hidden in the UI.
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

**The directory is open; the private half of a profile is not.** The wireframes show the employee
directory as the landing page for every role, so anyone can look a colleague up and open their profile —
name, photo, job position, department, manager, location and the resume are all meant to be seen. Date of
birth, home address, personal email, gender, marital status and bank details are not directory
information: an employee sees those on their own record, and Admin and HR see them on anyone's because
administering people requires it. The restriction is applied by serving a different serializer, so those
fields are never loaded for an unauthorised viewer rather than being fetched and then hidden by the
frontend.

**Employees are deactivated, never deleted.** Attendance and payroll are records of what a person was paid —
deleting an employee would erase the evidence behind payslips already issued and break statutory retention
requirements. Deactivation marks an account inactive (sign-in fails), hides it from the directory by default,
but keeps every record. The person can be reactivated if they return or were deactivated by mistake, and
their former manager or HR Officer can still open their profile to review history.

**Work hours are deducted by the employee's configured break.** The specification asks for attendance shown
against working time including breaks. An employee in the building 09:00–18:00 with a one-hour break has
worked eight hours, not nine. A salary structure's `break_time_hours` field controls this; if unset, one
hour is assumed. Days shorter than the break clamp at zero rather than going negative.

**Uploaded files return relative paths, not absolute URLs.** Inside Docker, the backend is reachable as
`backend:8000` from containers but not from a browser. Attachment URLs (sick leave certificates) and
avatar image URLs now return paths like `/media/avatars/...` that resolve against the origin the page was
loaded from. The frontend proxies `/media` to Django, so uploads are reachable either way.

**Login attempts are rate limited.** Login IDs follow a documented format and can be enumerated. Without a
limit on attempts, the password is the only barrier to an account. Sign-in allows ten attempts per minute —
generous for mistyping, useless for a script — with sign-up and password changes bounded too (5 and 10 per
minute respectively).
