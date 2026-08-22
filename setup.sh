#!/bin/sh
# Creates .env with freshly generated secrets. Run once, before the first `docker compose up`.
set -e

if [ -f .env ]; then
    echo ".env already exists — leaving it alone."
    exit 0
fi

python3 - <<'PYTHON' > .env
import base64
import secrets

print("DJANGO_SECRET_KEY=" + secrets.token_urlsafe(50))
print("DJANGO_DEBUG=True")
# Fernet requires a 32-byte key, url-safe base64 encoded.
print("FIELD_ENCRYPTION_KEY=" + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
print()
print("POSTGRES_DB=dayflow")
print("POSTGRES_USER=dayflow")
print("POSTGRES_PASSWORD=" + secrets.token_urlsafe(24))
print()
print("# Django connects as this restricted, non-superuser role so row-level security applies.")
print("APP_DB_USER=dayflow_app")
print("APP_DB_PASSWORD=" + secrets.token_urlsafe(24))
PYTHON

echo "Wrote .env with generated secrets."
echo "Next: docker compose up --build"
