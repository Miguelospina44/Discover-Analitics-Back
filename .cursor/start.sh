#!/usr/bin/env bash
# Per-boot runtime reconciliation: bring PostgreSQL online, ensure the
# application database exists, and apply migrations. Idempotent; returns
# once the database is ready so terminals can start the app servers.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACK_DIR="$(dirname "$SCRIPT_DIR")"

PG_VERSION="$(pg_lsclusters -h 2>/dev/null | awk 'NR==1{print $1}')"
PG_VERSION="${PG_VERSION:-16}"

echo "==> Starting PostgreSQL cluster ${PG_VERSION}/main"
if ! pg_lsclusters -h 2>/dev/null | awk '{print $4}' | grep -q online; then
  sudo pg_ctlcluster "${PG_VERSION}" main start || true
fi

echo "==> Waiting for PostgreSQL to accept connections"
for _ in $(seq 1 30); do
  if sudo -u postgres pg_isready -q; then
    break
  fi
  sleep 1
done

echo "==> Ensuring role password and application database"
sudo -u postgres psql -v ON_ERROR_STOP=1 -c "ALTER USER postgres WITH PASSWORD 'change-me';" >/dev/null
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='discover_analytics'" | grep -q 1; then
  sudo -u postgres createdb discover_analytics
  echo "    created database discover_analytics"
fi

echo "==> Applying Alembic migrations"
cd "$BACK_DIR"
# shellcheck disable=SC1091
. .venv/bin/activate
alembic upgrade head
deactivate

echo "==> start.sh complete; database ready"
