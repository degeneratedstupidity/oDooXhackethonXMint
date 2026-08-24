# Dayflow — project notes

Everything about how this system is built, the problems that came up while building it and
how each was resolved, and the questions worth being ready for.

Written as a reference for myself. `README.md` is the front door for someone running the
project; this is the reasoning underneath it.

---

## 1. What the project is

A multi-tenant Human Resource Management System built for the Odoo Hackathon. Any company
signs up, gets a fully isolated slice of the database, and manages its own employees,
attendance, leave and payroll.

**Scope delivered**

| Area | What it does |
| --- | --- |
| Companies | Sign-up creates a company and its first Admin |
| Employees | Created by Admin/HR, never self-registered; auto-generated login ID and first password |
| Directory | Searchable grid, status dot, department pill |
| Profile | Four tabs — Resume, Private Info, Salary Info, Security |
| Attendance | Check in/out, work hours net of break, extra hours, day and month views |
| Time off | Requests, approve/refuse, per-type balances, year calendar with public holidays |
| Payroll | Salary structure with components derived from wage, PF and professional tax, payslips from real attendance |

**Roles** — Admin (everything, including salary), HR Officer (people, attendance, leave —
but *not* salary), Employee (their own records only).

---

## 2. Stack and why

| Layer | Choice | Reason |
| --- | --- | --- |
| Backend | Django 5.1 + DRF 3.15 | Batteries-included admin, ORM, migrations, auth. DRF serializers give one place to validate every write. |
| Database | PostgreSQL 16 | Row-Level Security. No other mainstream DB enforces tenant isolation this cleanly. |
| Frontend | Next.js App Router + TypeScript + Tailwind | Server components for the shell, typed API responses, one utility system instead of hand-rolled CSS. |
| Auth | `djangorestframework-simplejwt` | Stateless tokens, no session table, works cleanly across the container boundary. |
| Encryption | `cryptography` (Fernet) | AES-128-CBC + HMAC. Authenticated, so tampering is detected, not just hidden. |
| Runtime | Docker Compose | Three services, one command. No "works on my machine". |

Total dependency list is eight packages. Everything else is standard library or framework.

---

## 3. Architecture

```
┌──────────┐      /api proxy      ┌──────────┐                ┌──────────┐
│ Next.js  │ ───────────────────▶ │  Django  │ ─────────────▶ │ Postgres │
│  :3000   │      /media proxy    │  :8000   │   RLS-scoped   │  :5432   │
└──────────┘                      └──────────┘   connection   └──────────┘
```

Next proxies `/api` and `/media` to Django. The browser only ever talks to `localhost:3000`,
which is what makes relative media URLs work (see problem 7).

**Django apps**

- `accounts` — `Company`, `User`, `EmployeeProfile`, `BankDetail`, tenancy, RLS helpers
- `attendance` — `Attendance`
- `timeoff` — `TimeOffType`, `TimeOffRequest`, `PublicHoliday`
- `payroll` — `SalaryStructure`, `SalaryComponent`, payslip computation

---

## 4. The two security mechanisms

### Row-Level Security — tenant isolation

Every company-owned table carries a `company_id` and gets one identical policy:

```sql
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
    USING (company_id = NULLIF(current_setting('app.current_company_id', true), '')::bigint)
    WITH CHECK (company_id = NULLIF(current_setting('app.current_company_id', true), '')::bigint);
```

The session variable is set once per request, in DRF's `initial()`:

```python
cursor.execute("SELECT set_config('app.current_company_id', %s, true)", [company_id])
```

The point: a query **physically cannot** return another company's rows, no matter what the
ORM asks for. Application filters are the first line of defence; this is the one that holds
when a developer forgets one.

### Field-level encryption — sensitive PII

`EncryptedCharField` encrypts on the way in and decrypts on the way out, so Postgres only
ever stores ciphertext. Applied to bank account number, IFSC, PAN and UAN.

The deliberate limit: encrypted columns can't be filtered or sorted in SQL. That is fine
for these four fields, which are displayed and edited but never searched. Salary figures
are *not* encrypted, because payroll does arithmetic on them — they're protected by RLS
plus an Admin-only permission instead.

---

## 5. Problems faced, and how each was solved

The interesting part. Each of these was a real bug or design conflict, not a hypothetical.

### 1. RLS would have made login impossible

**Problem.** The plan was one RLS policy on every table. But authentication resolves a user
*by login ID*, before anyone knows which company they belong to. With a policy on
`accounts_user`, that lookup returns zero rows and every login fails — a chicken-and-egg
deadlock.

**Fix.** Deliberately exclude `accounts_user` from RLS and scope it in the application
layer instead: every endpoint that lists or resolves users filters on
`request.user.company`. All the *sensitive* per-employee data — profile, bank details,
attendance, leave, payroll — lives in tables that are covered.

**Lesson.** RLS protects data tables. The identity table it authenticates against has to sit
outside it, by necessity.

### 2. `SET LOCAL` in middleware silently did nothing

**Problem.** The tenant scope was originally set in Django middleware. Queries returned zero
rows everywhere.

**Cause.** Two things compounding. DRF authenticates *lazily, inside the view*, so
`request.user` is still anonymous while middleware runs. And `ATOMIC_REQUESTS` wraps only
the view in a transaction — `SET LOCAL` is scoped to the surrounding transaction, so a value
set in middleware applied to a different transaction and was discarded before any real query.

**Fix.** Move it into DRF's `initial()`, which runs *after* authentication and *before* the
handler, inside the right transaction. Implemented as `TenantScopedMixin`.

**Lesson.** `SET LOCAL` and transaction boundaries have to agree. Knowing *where* in the
request lifecycle authentication happens is the whole ballgame.

### 3. RLS policies were decorative without `FORCE`

**Problem.** Policies were enabled, but a cross-company query still returned rows.

**Cause.** In Postgres, the **table owner bypasses RLS by default**. Django connected as the
owner, so every policy was ignored.

**Fix.** Two changes — add `FORCE ROW LEVEL SECURITY` to every table, and have Django connect
as a *restricted non-superuser role* (`dayflow_app`, created by `db/init.sh`). A superuser
bypasses RLS by design, so connecting as one would have defeated it anyway.

**Lesson.** Enabling RLS is not the same as enforcing it. This is the single easiest way to
ship a multi-tenant app that only *looks* isolated.

### 4. The specification contradicted itself on salary

**Problem.** The spec states `Fixed allowance = wage − total of all other components`, but
the accompanying mockup shows ₹2,918.00 against a ₹50,000 wage. Those don't agree — the
mockup's own components sum to ₹48,750, leaving ₹1,250 unaccounted, while the stated rule
yields ₹4,168.

**Fix.** Implement the **rule**, not the illustration. The spec separately requires that
components never exceed the wage, and only the rule guarantees they sum to *exactly* the
wage at every value. Every other component matches the mockup precisely (Basic ₹25,000,
HRA ₹12,500, Standard ₹4,167, Bonus/LTA ₹2,082.50) — documented the discrepancy in the
README rather than quietly picking one.

**Lesson.** When a spec conflicts with itself, implement the invariant, and write down why.

### 5. Any employee could read a colleague's bank details

**Problem — the most serious bug found.** `GET /employees/{id}/` returned
`EmployeeDetailSerializer` to *any* authenticated user in the company, for *any* employee.
That included date of birth, home address, personal email — and bank account number, IFSC,
PAN and UAN. The frontend showed the fields disabled, which prevented editing but not
reading, and the API returned everything regardless.

The encryption was working perfectly and protecting nothing: the data was encrypted at rest,
then handed to whoever asked.

**Fix.** Choose the serializer by viewer, not by action. Self, Admin and HR get the full
record; everyone else gets work information and resume only. The fields are **absent from
the response body**, not blanked — nothing sensitive is serialised for someone who may not
see it. The frontend hides the Private Info tab to match.

**Lesson.** Encryption at rest answers "what if the database leaks", not "who may read
this". They are separate controls and both are needed. Also: a disabled input is a UI hint,
never an access control.

### 6. Login IDs are enumerable by design

**Problem.** The format is `[company code][initials][join year][sequence]` — every part
guessable. Anyone who knows one employee's name can construct their login ID. Without a
limit, the password is the only barrier and a script gets unlimited attempts.

**Fix.** DRF `ScopedRateThrottle` — 10/min on sign-in, 5/min on sign-up, 10/min on password
change. Generous for a human mistyping, useless for a script. Also kept the error message
**identical** whether the password is wrong or the account doesn't exist, so it can't be
used as an account-existence oracle.

**Known limitation, worth stating:** throttle counters live in the default in-memory cache,
which is per process. A multi-worker deployment needs Redis or Memcached, or each worker
keeps its own count and the effective limit multiplies. Noted in `settings.py`.

### 7. Uploaded files were unreachable from the browser

**Problem.** Avatars and leave attachments uploaded fine but rendered broken.

**Cause.** DRF builds absolute URLs from the request host. Inside Docker that host is
`backend:8000` — reachable from the frontend *container*, meaningless to a browser.

**Fix.** `RelativeFileURLMixin`, returning `value.url` (a path like `/media/avatars/…`)
instead of an absolute URL. It resolves against whatever origin served the page, and Next
proxies `/media` to Django, so it works in both directions.

**Lesson.** Container hostnames and browser-reachable hostnames are different namespaces.
Anything the browser will fetch must be expressed in *its* namespace.

### 8. Configured break time was stored but never used

**Problem.** `SalaryStructure.break_time_hours` existed, was editable, and was ignored.
Work hours were raw clock time, compared against a hardcoded 8.

**Fix.** `work_hours = attended_hours − break_hours`, falling back to one hour when no
salary structure exists. Someone in the building 09:00–18:00 with a one-hour break has
worked eight hours, not nine. Clamped at zero so a day shorter than the break can't go
negative.

**Lesson.** A field that is stored and displayed but never *used* is a bug with a UI.

### 9. Deleting a company failed on foreign keys

**Problem.** `seed_demo --reset` crashed deleting the existing company.

**Cause.** Django's cascade collector queries for related rows to delete — but with the
tenant scope unset, RLS hid those rows from the collector. It saw nothing to cascade, issued
the delete, and Postgres refused on a foreign key that pointed at rows Django couldn't see.

**Fix.** Set the scope to the company being deleted *first*, so the collector sees its rows,
then tear down explicitly in dependency order.

**Lesson.** RLS applies to framework internals too, not just to code you wrote. Anything
relying on "query everything" breaks under it.

### 10. `/api/me/` returned an empty profile

**Problem.** Job position, department and location came back blank for everyone.

**Cause.** `MeView` is an `APIView`, not a viewset, and never had the tenancy mixin applied.
With no scope set, RLS hid the `EmployeeProfile` row — so the join found nothing and the
fields serialised as empty. No error, just silently blank.

**Fix.** Apply `TenantScopedMixin` (which works on any DRF view via `initial()`), plus a
regression test asserting the fields populate.

**Lesson.** RLS failures are *silent* — empty results, not exceptions. That makes them
harder to spot than a crash and worth a test each.

### 11. Reactivating an employee 404'd

**Problem.** Deactivation worked; reactivation could never find the employee.

**Cause.** `get_queryset()` filtered out inactive users so they'd vanish from the directory.
But the same queryset backs detail lookups — so the one endpoint that exists to un-deactivate
someone couldn't see anyone deactivated.

**Fix.** Apply the active filter only when `action == "list"`, leaving detail lookups
unfiltered.

**Lesson.** A queryset serving both list and detail needs to know which one it's serving.

### 12. The leave calendar hid overlapping leave

**Problem.** The calendar kept `Map<string, Request>` — **one request per date**. When two
people were off the same day, one silently overwrote the other. On an admin's calendar that
is the *normal* case.

**Fix.** Key each date to a *list*. Hovering or focusing a day lists everyone away, grouped
by approved / awaiting decision / refused, with a count badge on busy days. Click pins it
open, because hover doesn't exist on touch screens. Names show to Admin/HR only.

Also added overlapping leave to the seed data — none of it overlapped before, so the case
would never have appeared in a demo.

**Lesson.** A `Map` keyed on something non-unique is a data-loss bug wearing a lookup's
clothing.

### 13. A fresh clone can't log in

**Problem.** Someone cloned the repo, started it, and couldn't sign in with the documented
credentials.

**Cause.** Not a bug. `docker compose up` creates an *empty* database. The demo accounts only
exist after `seed_demo` runs — they aren't in the repo. And because the error message is
deliberately identical for "wrong password" and "no such account", it can't say so.
Retrying more than ten times then triggers the throttle, producing a *second*, different
error that looks like a new problem.

**Fix.** Documentation, not code: a "You need an account before you can sign in" section and
a troubleshooting list covering exactly this chain.

**Lesson.** A security property that's right (no account-existence oracle) can make setup
harder to self-diagnose. The answer is docs, not weakening the property.

### 14. My own diagnostic tool lied to me

**Problem.** Checking seeded leave via `manage.py shell` reported **zero** requests. I
briefly concluded the seeder was broken.

**Cause.** The shell runs in autocommit. `SET LOCAL` outside a transaction does nothing, so
the tenant scope was never applied and RLS hid every row. The data was there the whole time —
querying the same thing through the API returned all nine.

**Lesson.** Verify through the real code path. An ad-hoc shell doesn't reproduce the
request lifecycle, and a diagnostic that bypasses your own security model will lie to you.
Worth stating plainly because I acted on the wrong conclusion before catching it.

---

## 6. Testing

96 tests, all against a real PostgreSQL instance — never SQLite, because the whole security
model is Postgres-specific and SQLite would test nothing that matters.

| App | Tests | Covers |
| --- | --- | --- |
| `accounts` | 13 | Login ID sequencing, RLS isolation, encryption at rest, profile visibility, deactivation |
| `attendance` | 15 | Check in/out rules, work hours net of break, extra hours |
| `timeoff` | 14 | Overlap detection, approval workflow, balances, holidays |
| `payroll` | 21 | Component computation, the spec's worked example, payslips from attendance |

Two worth calling out:

- **RLS tests run against the real policies** — the test database is built by the same
  migrations, and Django connects as the same restricted role. They fail if isolation ever
  regresses.
- **Encryption tests read the raw database column** to confirm ciphertext is stored, rather
  than trusting the ORM to round-trip a value it just wrote.

---

## 7. Questions to be ready for

### Technical — architecture

**Why Row-Level Security instead of just filtering in Django?**
Application filters depend on every developer remembering them on every endpoint, forever.
One forgotten `.filter(company=...)` leaks another company's data. RLS makes the leak
*physically impossible* — the database won't return the rows. Defence in depth: I still
filter in the application, but that's the first line, not the only one.

**Why exclude the user table from RLS?**
Authentication resolves a user by login ID before their company is known. A policy on that
table means the lookup returns zero rows and every login fails. It's scoped in the
application layer instead, and every table holding sensitive data *is* covered.

**How does a request get scoped to a tenant?**
DRF's `initial()` runs after authentication, inside the `ATOMIC_REQUESTS` transaction, and
calls `set_config('app.current_company_id', <id>, true)`. `is_local => true` means it lasts
until the transaction ends, so it can't leak into the next request on a pooled connection.

**What breaks if you get that wrong?** I got it wrong first — see problem 2.

**Why is FORCE ROW LEVEL SECURITY necessary?**
The table owner bypasses RLS by default. Django connects as the owner, so without `FORCE`
every policy is decorative. I also connect as a restricted non-superuser, since superusers
bypass RLS by design.

**How do you handle migrations under RLS?**
Migrations run with no company set. `current_setting(..., true)` — the missing_ok form —
returns NULL rather than erroring, and NULL fails the comparison, so those sessions see no
rows. Schema changes work; data access doesn't, which is correct.

### Technical — security

**What's encrypted and what isn't, and why?**
Bank account number, IFSC, PAN, UAN — Fernet, encrypted at rest. Salary figures are not,
because payroll does arithmetic on them; they're protected by RLS plus an Admin-only
permission. Passwords are hashed, never encrypted — hashing is one-way and there is no
legitimate reason to recover a password.

**What's the cost of field-level encryption?**
Encrypted columns can't be filtered, sorted or indexed in SQL — the database only sees
ciphertext, so `WHERE pan_number = ...` cannot work. Acceptable for four fields that are
displayed and edited but never searched. It would be the wrong choice for anything you query
on.

**Tell me about a security bug you found in your own code.**
The strongest answer available — problem 5. Any employee could read any colleague's bank
account, PAN and UAN through the API. The frontend disabled the fields, which stopped editing
but not reading, and the API returned them regardless. Fixed by selecting the serializer by
*viewer* rather than by action, and omitting the fields entirely rather than blanking them.
The lesson: encryption at rest answers "what if the database leaks", not "who may read this",
and a disabled input is never an access control.

**Why rate-limit login when you already hash passwords?**
Because the login IDs are enumerable by construction — the format is documented and every
component is guessable. Hashing protects a stolen database; it does nothing against online
guessing. 10/min makes a script useless while barely inconveniencing a human. I also keep the
error message identical for "wrong password" and "no such account" so it can't be used to
confirm which IDs exist.

**What would you change before production?**
Four things, in order. Move throttle counters to Redis — they're in per-process memory now,
so multiple workers multiply the effective limit. Add key rotation for the Fernet key, since
there's currently one key and no re-encryption path. Serve media through the web server
rather than Django. Add refresh-token rotation — the frontend has an 8-hour access token and
doesn't currently refresh.

### Technical — product

**Walk me through the salary computation.**
Components are a percentage of wage, a percentage of basic, or a fixed amount. Order matters:
basic resolves first because other components are percentages *of* it, then everything else,
then Fixed Allowance takes whatever the wage has left. That guarantees components sum to
exactly the wage at any value. Changing the wage recomputes everything, so stored amounts
can't drift.

**The spec's example didn't match its own rule — what did you do?**
Implemented the rule, because the spec separately requires components never exceed the wage
and only the rule guarantees that. Documented the discrepancy in the README instead of
silently choosing.

**How is a payslip derived?**
Working days in the month minus weekends and company public holidays; then unpaid leave and
unaccounted days (no attendance, no approved leave, not a holiday) reduce payable days.
A holiday is never an absence — nobody loses pay for a day they weren't expected to work.

**Why deactivate employees instead of deleting them?**
Attendance underpins payslips already issued. Deleting an employee erases the evidence behind
real payments and breaks statutory retention. Deactivation blocks sign-in and hides them from
the directory while keeping every record, and it's reversible.

### Behavioural / HR

**What was the hardest problem?**
Problem 2 — the tenant scope silently doing nothing. Everything looked correct and every
query returned empty. It needed understanding two interacting things: DRF authenticating
lazily inside the view, and `SET LOCAL` being scoped to a transaction that hadn't started
yet. Nothing errored, which is what made it hard.

**Tell me about a mistake you made.**
Two, honestly. The bank-details leak (problem 5) — I'd built encryption and assumed the data
was protected, when the API was handing it to anyone who asked. And problem 14: my own
diagnostic shell reported zero seeded records and I briefly concluded the seeder was broken,
when the shell was bypassing the tenant scope and RLS was correctly hiding everything. Wrong
conclusion from a tool I trusted. Both taught the same thing — verify through the real code
path, not a convenient shortcut.

**How did you decide what to cut?**
Ordered by what a judge would actually exercise. Correctness and security first, because they
are invisible when right and disqualifying when wrong. Cosmetic polish last. Two things I
deliberately did *not* finish — the responsive pass at 375/768/1280px and the calendar
panel's placement at narrow widths — are written down in `docs/TEST-LOG.md` as unverified
rather than quietly assumed fine.

**You worked solo — how did you handle that?**
The registration rules allow a team of one. I wrote up isolated task cards
(`docs/TASK-CARDS.md`) so teammates could contribute without reading the whole codebase, and
when they stayed unavailable I did the work and said so plainly. I didn't manufacture commits
under their names — that misrepresents contribution to the people evaluating it, and it's
trivially visible in a repo this small.

**What are you proudest of?**
That the security is real and provable rather than claimed. The RLS tests run against the
actual policies as the actual restricted role, and the encryption test reads the raw database
column instead of trusting the ORM. If tenant isolation regresses, the suite fails.

**What would you do differently?**
Write the permission tests before the endpoints. Every access-control bug I found — the bank
details leak, the reactivation 404 — would have surfaced immediately. I tested computation
logic first because it was more obviously testable, and the authorization gaps sat there
longer than they should have.

---

## 8. Honest limitations

Worth stating before someone finds them.

- **Throttle counters are per process.** In-memory cache; a multi-worker deployment needs
  Redis or the limit multiplies.
- **No refresh-token rotation in the frontend.** The 8-hour access token covers a demo; a
  real deployment needs refresh handling.
- **One encryption key, no rotation path.** Rotating means re-encrypting every row.
- **Media served by Django.** Fine in `DEBUG`; production needs the web server.
- **Responsive layout unverified in a browser** at 375/768/1280px, along with the calendar
  panel's placement at narrow widths. Both recorded in `docs/TEST-LOG.md`.
