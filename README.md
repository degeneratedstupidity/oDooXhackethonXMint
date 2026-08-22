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
cp .env.example .env    # then edit values
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api

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

## Project layout

```
backend/     Django project — API, models, migrations
frontend/    Next.js app
```

## Design decisions

Where the specification left room for interpretation, the reasoning behind our choices is documented here
as the project develops.
