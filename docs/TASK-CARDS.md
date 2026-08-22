# Task cards

Self-contained pieces of work that can be picked up without reading the whole codebase.
Each one names the files to touch, what "done" looks like, and how to check it.

**Before starting any card**

```bash
git pull origin main
docker compose up -d          # needs Docker Desktop running
docker compose exec backend python manage.py seed_demo --reset
```

Sign in at http://localhost:3000 as `OIASME20220001` (Admin) — password `Demo@2026`.
The seed command prints logins for the HR officer and employees too.

**When you finish**

```bash
git add <the files you changed>
git commit -m "Short description of what changed"
git push origin main
```

Commit under your own name — check `git config user.name` and `git config user.email` are
yours before your first commit.

---

## Card 1 — Public holiday calendar — **done**

Implemented already; left here for reference.

**Why:** Time off is counted in plain calendar days right now, so a request spanning a
public holiday burns a day of the employee's allowance that it should not.

**Files:** `backend/timeoff/models.py`, a new migration, `backend/accounts/seed.py`

1. Add a `PublicHoliday` model — company-scoped (inherit `TenantScopedModel`), with `name`
   and `date`.
2. Add the RLS migration for it, copying `backend/timeoff/migrations/0002_enable_rls.py`
   and changing the table name to `timeoff_publicholiday`.
3. Seed the 2026 Indian public holidays in `seed.py` alongside the leave types
   (Republic Day, Holi, Independence Day, Gandhi Jayanti, Diwali — the specification's
   mockup lists a full set).

**Done when:** a new company is created and `GET /api/time-off-types/` still works, and
the holidays exist in the database for that company only.

**Check:** `docker compose exec backend python manage.py shell` then
`from timeoff.models import PublicHoliday; PublicHoliday.objects.count()`

---

## Card 2 — Employee card polish

**Why:** The directory is the landing page and the first thing a judge sees.

**File:** `frontend/components/Avatar.tsx` and the card markup in
`frontend/app/employees/page.tsx`

1. Give the initials avatar a deterministic background colour derived from the name, so
   each person is visually distinct. Pick from the `brand`/`ink` tokens already defined in
   `frontend/app/globals.css` — do not introduce new colours.
2. Show the employee's department on the card as a small pill.
3. Make sure the card still truncates cleanly at narrow widths (test at 375px).

**Done when:** the grid looks right at 375px, 768px and 1280px with no horizontal page
scroll.

---

## Card 3 — API documentation

**Why:** The README describes the product but not the API surface.

**File:** new `docs/API.md`

Document each endpoint with method, path, who may call it, an example request body and an
example response. The endpoints are registered in `backend/*/urls.py`. Get real examples by
calling the API with `curl` against the seeded data rather than inventing them.

**Done when:** someone can drive the whole API from the document alone.

---

## Card 4 — Manual test pass

**Why:** Nobody has clicked through every screen as every role.

**File:** new `docs/TEST-LOG.md`

Sign in as each of the three roles and work through every page: directory, search, adding
an employee, check in/out, attendance views, requesting time off, approving and refusing,
every profile tab, changing a password. Record what you did and what happened. Anything
broken or awkward goes in the file with the steps to reproduce it.

**Done when:** every screen has been exercised as all three roles and the log is committed.
