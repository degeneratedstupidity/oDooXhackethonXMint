"""Enable Postgres Row-Level Security on every company-owned table.

Application-layer checks (DRF permissions and scoped querysets) are the first line of
defence, but they are only as good as the developer remembering them on every endpoint.
These policies make cross-company data leakage impossible at the database level: a query
physically cannot return another company's rows, regardless of what the ORM asks for.

The session variable `app.current_company_id` is set per request in accounts/tenancy.py.

Two details that matter:

* FORCE ROW LEVEL SECURITY — without it, the table owner (which is the role Django
  connects as) bypasses RLS entirely and the policies would be decorative.
* The `app.current_company_id` lookup uses `current_setting(..., true)`, the missing_ok
  form, so management commands and migrations that run with no company set get NULL
  rather than an error. NULL fails the comparison, so those sessions see no rows unless
  they are running as a superuser, which bypasses RLS by design.

`accounts_user` is deliberately NOT in this list. Authentication has to find a user by
login ID *before* anyone knows which company they belong to, so a scoped policy on that
table would make every login fail — the lookup would return zero rows. The user table is
therefore scoped in the application layer instead: every endpoint that lists or resolves
users filters on `request.user.company`. The sensitive per-employee data — profile
details, bank and statutory identifiers, and later attendance, time off and payroll —
all live in tables that *are* covered here.
"""

from django.db import migrations

# Tables holding rows owned by exactly one company.
TENANT_TABLES = [
    "accounts_employeeprofile",
    "accounts_bankdetail",
]


def rls_sql(table):
    return f"""
        ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
        CREATE POLICY {table}_tenant_isolation ON {table}
            USING (company_id = NULLIF(current_setting('app.current_company_id', true), '')::bigint)
            WITH CHECK (company_id = NULLIF(current_setting('app.current_company_id', true), '')::bigint);
    """


def reverse_sql(table):
    return f"""
        DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
        ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
    """


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=rls_sql(table), reverse_sql=reverse_sql(table))
        for table in TENANT_TABLES
    ]
