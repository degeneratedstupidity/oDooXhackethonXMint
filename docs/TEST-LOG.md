# Verification log

What has been exercised against the running stack, and what has not.

Run date: 22 August 2026. Stack: `docker compose up` with the seeded demo company.

## Automated

```
docker compose exec backend python manage.py test
Ran 72 tests — OK
```

Covering login ID format and sequencing, salary computation including the specification's
worked example, payslip derivation from attendance, time off validation and approval,
attendance hours, role permissions, row-level security against the real policies, and
encryption at rest verified by reading the raw column.

## Manual — API, through the frontend proxy

Every call below went to `http://localhost:3000/api/...`, the same path the browser uses,
so the proxy and the API contract are both covered.

### Read paths

| Endpoint | Admin | HR Officer | Employee |
| --- | --- | --- | --- |
| `/me/` | 200 | 200 | 200 |
| `/employees/` | 200 | 200 | 200 |
| `/employees/{id}/` | 200 | 200 | 200 |
| `/attendance/today/` | 200 | 200 | 200 |
| `/attendance/?date=` | 200 | 200 | 200 |
| `/attendance/?month=` | 200 | 200 | 200 |
| `/time-off/` | 200 | 200 | 200 |
| `/time-off/balances/` | 200 | 200 | 200 |
| `/salary/` | 200 | **403** | **403** |
| `/payslip/{id}/` | 200 | **403** | **403** |

Row counts confirm scoping rather than only status codes: with the seeded company, Admin
and HR each see 130 attendance rows and 6 time off requests, while an employee sees 17 and
2 — their own.

### Write paths

| Action | Result |
| --- | --- |
| Employee submits a 4-day leave request | 201, status `to_approve`, `days: 4` |
| Employee tries to approve their own request | **403** |
| Admin approves it | 200, status `approved` |
| Employee's balance afterwards | used 4, available 20 of 24 |
| Admin adds an employee | 201, login ID `OISMTE20260002`, password returned once |
| Admin sets a wage of ₹60,000 | components rebalance, total exactly ₹60,000 |
| New employee signs in with generated password | `must_change_password: true` |
| That employee sets their own password | flag clears, sign-in with the new password works |
| Employee uploads someone else's picture | **403** |

### Validation refusals

| Input | Response |
| --- | --- |
| Mismatched passwords at sign-up | `confirm_password: Passwords do not match.` |
| Single-word name at sign-up | `name: Enter both a first and last name…` |
| Weak password | Django's validators, all failures listed |
| Leave ending before it starts | `end_date: The end date cannot be before the start date.` |
| Leave overlapping an existing request | `non_field_errors: You already have a time off request…` |
| Sick leave with no certificate | `attachment: Sick Leave requires a supporting document.` |
| Wage below the committed components | `non_field_errors:` states the shortfall in rupees |
| Negative wage | `monthly_wage: Ensure this value is greater than or equal to 0.` |
| IFSC that is not 11 characters | `bank_detail.ifsc_code: An IFSC code is 11 characters long.` |
| Account number containing letters | `bank_detail.account_number: …digits only.` |
| Checking in twice in one day | `You have already checked in today.` |
| Checking out without checking in | `You have not checked in today.` |

### Cross-company isolation

A second company was created and its administrator confirmed to see only their own
employee. Requesting another company's employee by id returns 404, and at the database
level a query naming the other company's id returns zero rows.

## Pages

All render without a compile or runtime error: `/login`, `/signup`, `/change-password`,
`/employees`, `/employees/{id}`, `/attendance`, `/time-off`, `/profile`.

## Not yet verified

- **Visual review in a browser.** Layout, spacing and the responsive behaviour at 375 /
  768 / 1280 px have not been looked at by a person. The markup uses a single token
  palette and tables scroll inside their own container, but that is not a substitute for
  someone opening the pages.
- Uploading a real photograph or company logo through the browser file picker; the upload
  endpoint itself is verified with a generated PNG.
- Behaviour when an access token expires mid-session.
