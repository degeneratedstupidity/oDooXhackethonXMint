#!/bin/bash
# Creates the role Django connects as. Runs once, on first initialisation of the volume.
#
# This is what makes row-level security real: a superuser bypasses every RLS policy, and so
# does a table owner unless the table is marked FORCE ROW LEVEL SECURITY. This role is
# neither a superuser nor exempt, so the tenant isolation policies in
# accounts/migrations/0002_enable_rls.py actually constrain it. It still owns the schema, so
# it can run migrations and create tables normally.
#
# The password comes from the environment so it is never committed to the repository.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- CREATEDB is granted only so the Django test runner can build its test database.
    -- It is unrelated to RLS: NOBYPASSRLS and NOSUPERUSER are what keep the tenant
    -- isolation policies binding on this role.
    CREATE ROLE ${APP_DB_USER} LOGIN PASSWORD '${APP_DB_PASSWORD}'
        NOSUPERUSER CREATEDB NOCREATEROLE NOBYPASSRLS;

    GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${APP_DB_USER};
    ALTER SCHEMA public OWNER TO ${APP_DB_USER};
    GRANT ALL ON SCHEMA public TO ${APP_DB_USER};
EOSQL
