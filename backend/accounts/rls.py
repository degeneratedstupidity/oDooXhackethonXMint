"""One row-level security policy template, applied by each app's migration.

Keeping the SQL in a single place means every company-owned table is protected the same
way, and a new table gets the same guarantee by adding one migration rather than by
hand-writing policy SQL again.

See accounts/migrations/0002_enable_rls.py for why the user table is excluded.
"""


def enable_rls(table):
    return f"""
        ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
        CREATE POLICY {table}_tenant_isolation ON {table}
            USING (company_id = NULLIF(current_setting('app.current_company_id', true), '')::bigint)
            WITH CHECK (company_id = NULLIF(current_setting('app.current_company_id', true), '')::bigint);
    """


def disable_rls(table):
    return f"""
        DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
        ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
    """
