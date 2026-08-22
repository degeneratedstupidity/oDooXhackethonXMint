# API reference

Base URL `http://localhost:8000/api` (or `/api` through the frontend, which proxies to it).

All responses are JSON. Every path ends in a trailing slash.

## Authentication

JWT bearer tokens. Sign in, then send the access token on every subsequent request:

```
Authorization: Bearer <access token>
```

Access tokens last 8 hours, refresh tokens 1 day.

### `POST /auth/signup/`

Creates a company and its first administrator. This is the only endpoint that creates an
account without an existing session — everyone else is added by an Admin or HR Officer.
Accepts `multipart/form-data` when sending a company logo.

```bash
curl -X POST http://localhost:8000/api/auth/signup/ \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Odoo India","name":"John Doe","email":"john@odoo.test",
       "phone":"9990001111","password":"Str0ngPass!2026","confirm_password":"Str0ngPass!2026"}'
```

`201 Created`

```json
{
  "user": {
    "id": 1, "login_id": "OIJODO20260001", "full_name": "John Doe",
    "role": "admin", "company_name": "Odoo India", "must_change_password": false
  },
  "tokens": { "access": "eyJhbGci…", "refresh": "eyJhbGci…" }
}
```

`400` on validation failure, per field:

```json
{"confirm_password": ["Passwords do not match."]}
{"name": ["Enter both a first and last name — the login ID is built from them."]}
```

### `POST /auth/login/`

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"login_id":"OIASME20220001","password":"Demo@2026"}'
```

`200` → `{"access": "…", "refresh": "…"}`, `401` on bad credentials.

### `POST /auth/refresh/`

`{"refresh": "…"}` → `{"access": "…"}`.

### `POST /auth/change-password/`

Any signed-in user, for their own password. Clears `must_change_password`.

```json
{"current_password": "…", "new_password": "…", "confirm_password": "…"}
```

`200` → `{"detail": "Password updated."}`

### `GET /me/`

The signed-in user.

```json
{
  "id": 8, "login_id": "OIASME20220001", "full_name": "Asha Menon",
  "email": "asha.menon@oi.example", "role": "admin",
  "date_of_joining": "2022-01-01", "must_change_password": false,
  "company_name": "Odoo India", "job_position": "Chief People Officer",
  "department": "Leadership", "work_status": "absent"
}
```

## Employees

### `GET /employees/`

The directory. Every role may read it; results are always confined to the caller's company.
Optional `?search=` matches name, login ID, email, job position and department.
Deactivated employees are excluded unless `?include_inactive=true` is passed.

```json
[{
  "id": 10, "login_id": "OIPRNA20240001", "full_name": "Priya Nair",
  "email": "priya.nair@oi.example", "role": "employee",
  "job_position": "Senior Engineer", "department": "Engineering",
  "work_status": "absent"
}]
```

`work_status` is one of `present` (checked in today), `leave` (an approved request covers
today) or `absent`.

### `DELETE /employees/{id}/` — Admin, HR Officer

Deactivates rather than deletes. The account stops working and drops out of the directory
listing, but attendance, leave and salary records are kept — they are the evidence behind
payslips already issued. `403` when aimed at your own account.

### `POST /employees/{id}/reactivate/` — Admin, HR Officer

Restores a deactivated employee.

### `POST /employees/` — Admin, HR Officer

Adds an employee. The login ID and first password are generated, never supplied.

```json
{"first_name":"Priya","last_name":"Nair","email":"priya@oi.test","role":"employee",
 "date_of_joining":"2026-03-01","job_position":"Engineer","department":"Engineering"}
```

`201 Created` — the password is returned once and never again:

```json
{
  "user": { "...": "as above" },
  "credentials": { "login_id": "OIPRNA20260002", "password": "6v8Um85Lsbtq" }
}
```

`403` for the Employee role.

### `GET /employees/{id}/`

The profile page. What comes back depends on who is asking:

- **The employee themselves, an Admin, or an HR Officer** get the full record — identity,
  work information, private information (date of birth, residing address, nationality,
  personal email, gender, marital status) and `bank_detail`.
- **Anyone else in the company** gets identity, work information and the resume fields
  only. The private block and `bank_detail` are **absent from the response**, not blanked —
  they are never serialised.

`404` if the id belongs to another company.

### `PATCH /employees/{id}/`

An employee may edit their own record; Admin and HR may edit anyone's. Only an
administrator may set someone else's `role`, and nobody may change their own.

```json
{
  "phone": "9876543210",
  "profile": {"job_position": "Head of People", "skills": ["Recruiting"]},
  "bank_detail": {"bank_name": "HDFC Bank", "account_number": "998877665544",
                  "ifsc_code": "HDFC0001234", "pan_number": "ABCPI1234K"}
}
```

Bank and statutory fields are encrypted at rest. Validation errors nest under their section:

```json
{"bank_detail": {"ifsc_code": ["An IFSC code is 11 characters long."]}}
```

## Attendance

### `GET /attendance/`

Employees see their own records; Admin and HR see everyone's.
Filters: `?date=YYYY-MM-DD`, `?month=YYYY-MM`, `?user={id}` (Admin/HR only).

```json
[{
  "id": 1, "employee_name": "Priya Nair", "login_id": "OIPRNA20240001",
  "date": "2026-08-21", "check_in": "2026-08-21T09:30:00+05:30",
  "check_out": "2026-08-21T18:30:00+05:30",
  "attended_hours": 9.0, "break_hours": "1.00", "work_hours": 8.0, "extra_hours": 0.0
}]
```

All four figures are derived from the timestamps, not stored. `attended_hours` is time on
the premises; `work_hours` takes off the employee's configured break, so 09:30–18:30 with
an hour's break is eight hours worked. `extra_hours` is whatever exceeds an eight-hour day,
and never negative.

### `GET /attendance/today/`

The caller's record for today, or `null`. Drives the check in / check out control.

### `POST /attendance/check_in/`

`201` with the new record. `400 {"detail": "You have already checked in today."}`.

### `POST /attendance/check_out/`

`200` with the closed record. `400` if not checked in, or already checked out.

## Time off

### `GET /time-off-types/`

The company's leave types, seeded on sign-up.

```json
[{"id":7,"name":"Paid Time Off","is_paid":true,"default_days_per_year":24.0,"requires_attachment":false},
 {"id":8,"name":"Sick Leave","is_paid":true,"default_days_per_year":7.0,"requires_attachment":true},
 {"id":9,"name":"Unpaid Leave","is_paid":false,"default_days_per_year":0.0,"requires_attachment":false}]
```

### `GET /time-off/`

Employees see their own requests; Admin and HR see everyone's. Filters `?status=`, `?user=`.

Each request carries `employee_name` and `type_name` alongside the dates and status, which
is what the leave calendar uses to list the people away on a given day. Because Admin and
HR receive the whole company's requests from this one call, the calendar needs no extra
endpoint.

### `POST /time-off/`

`multipart/form-data` when attaching a document.

```json
{"type": 7, "start_date": "2026-09-01", "end_date": "2026-09-03", "reason": "Family event"}
```

`201` with `status: "to_approve"` and a computed `days` (inclusive of both dates).

Rejections:

```json
{"end_date": ["The end date cannot be before the start date."]}
{"attachment": ["Sick Leave requires a supporting document."]}
{"non_field_errors": ["You already have a time off request covering some of those dates."]}
```

### `POST /time-off/{id}/approve/` · `POST /time-off/{id}/refuse/` — Admin, HR Officer

`200` with the updated request. `400` if it has already been decided. `403` for employees.

### `GET /time-off/balances/`

The caller's remaining days per type for the current year. Uncapped types report `null`
rather than a misleading number.

```json
[{"type":7,"name":"Paid Time Off","is_paid":true,"allowance":24.0,"used":3,"available":21.0},
 {"type":9,"name":"Unpaid Leave","is_paid":false,"allowance":null,"used":0,"available":null}]
```

## Salary — administrator only

Every endpoint below returns `403` for HR Officers and Employees alike.

### `GET /salary/`

Optional `?user={id}`.

```json
[{
  "id": 3, "user": 10, "employee_name": "Priya Nair",
  "monthly_wage": "95000.00", "yearly_wage": "1140000.00",
  "working_days_per_week": 5, "professional_tax": "200.00",
  "pf_employee_percent": "12.00", "pf_employee_amount": "5700.00",
  "components": [
    {"id": 13, "code": "basic", "label": "Basic Salary",
     "computation_type": "percent_of_wage", "value": "50.00", "amount": "47500.00"},
    {"id": 18, "code": "fixed", "label": "Fixed Allowance",
     "computation_type": "remainder", "value": "0.00", "amount": "7916.00"}
  ]
}]
```

### `PATCH /salary/{id}/`

Changing the wage recomputes every component, so the amounts can never drift.

```json
{"monthly_wage": "50000"}
```

On a ₹50,000 wage this yields Basic ₹25,000 (50% of wage), HRA ₹12,500 (50% of basic),
Standard ₹4,167, Performance Bonus and LTA ₹2,082.50 each, and Fixed Allowance ₹4,168 as
the remainder — summing to exactly the wage.

`400` when the components cannot fit:

```json
{"non_field_errors": ["Salary components total ₹6,666.90, which is more than the ₹3,000.00 wage. Lower a component before reducing the wage."]}
```

### `PATCH /salary/{id}/components/{component_id}/`

Change one component's basis, then rebalance the structure.

```json
{"computation_type": "percent_of_wage", "value": "40"}
```

### `GET /payslip/{user_id}/?year=2026&month=8`

Computed on request from attendance, approved leave and the salary structure — never
stored, so it cannot disagree with the records behind it.

```json
{
  "employee": "Priya Nair", "login_id": "OIPRNA20240001", "monthly_wage": 95000.0,
  "year": 2026, "month": 8,
  "working_days": 21, "days_present": 11,
  "paid_leave_days": 3, "unpaid_leave_days": 0, "unaccounted_days": 4,
  "payable_days": 17,
  "per_day_rate": 4523.81, "gross_pay": 76904.77,
  "deductions": {"provident_fund": 4614.29, "professional_tax": 200.0, "total": 4814.29},
  "net_pay": 72090.48,
  "components": [{"code": "basic", "label": "Basic Salary",
                  "full_amount": 47500.0, "earned": 38452.38}]
}
```

Unpaid leave and working days with no attendance reduce `payable_days`. Paid leave does
not. Days before the employee joined, and days still in the future, are not counted as
absence.

## Errors

| Status | Meaning |
| --- | --- |
| 400 | Validation failed. Body maps field names to messages; `non_field_errors` holds rule violations that span fields. |
| 401 | Missing, expired or invalid token. |
| 403 | Authenticated but not permitted — the role lacks access. |
| 404 | No such record **or** it belongs to another company. The two are deliberately indistinguishable. |
| 429 | Rate limited. Sign-in allows 10 attempts a minute, sign-up 5, password changes 10. |

## Tenant isolation

Every request is scoped to the caller's company by a Postgres session variable that
row-level security policies read, so a query cannot return another company's rows even if
application code omits a filter. Requesting another company's record by id returns `404`,
not `403`, so the API never confirms that an id exists elsewhere.
