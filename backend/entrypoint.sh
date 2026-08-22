#!/bin/sh
# Bring the database up to date before serving, so a fresh checkout works with a single
# `docker compose up` rather than needing a separate migrate step.
set -e

echo "Applying migrations…"
python manage.py migrate --noinput

exec "$@"
