#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
python - <<'PY'
import os, sys, time
import psycopg

for attempt in range(30):
    try:
        psycopg.connect(
            dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"], host=os.environ.get("POSTGRES_HOST", "db"),
            port=os.environ.get("POSTGRES_PORT", "5432"), connect_timeout=3,
        ).close()
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"  database not ready ({exc.__class__.__name__}), retrying...")
        time.sleep(2)
sys.exit("Database never became available")
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Optional demo data (fictional). Runs only on an empty database so restarts never wipe real edits.
if [ "${SEED_DEMO:-false}" = "true" ]; then
  python manage.py seed_demo || echo "Demo data already present, skipping."
fi

exec "$@"
