#!/usr/bin/env bash
# Schema contract test: the app's migrations vs. the orchestrator's view of the schema.
#
#  1. Starts a throwaway Postgres 14 in docker (or uses CONTRACT_PG_HOSTPORT, as CI
#     does with a service container).
#  2. Migrates it with the app's Alembic migrations to v1_9_0, seeds files, then
#     upgrades to head, downgrades to v1_9_0 and upgrades again (round trip), and
#     checks the file_key backfill.
#  3. Creates the orchestrator role twice (the second run proves it is idempotent).
#  4. Runs the orchestrator's `contract` tests against it.
#
# Needs poetry envs for servicex_app and servicex_orchestrator (with the test group).
# Usage: servicex_orchestrator/scripts/schema-contract-test.sh [extra pytest args]
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SCRIPTS="$ROOT/servicex_orchestrator/scripts"
PG_IMAGE=${PG_IMAGE:-postgres:14}
PG_DB=servicex
ADMIN_PASSWORD=${CONTRACT_PG_ADMIN_PASSWORD:-contract-admin}
ORCH_USER=servicex_orchestrator
# Deliberately awkward, to exercise quoting in the role command and the URL.
ORCH_PASSWORD="o'rch%pa\$\$ word"

if [ -z "${CONTRACT_PG_HOSTPORT:-}" ]; then
  CONTAINER=$(docker run -d --rm \
    -e POSTGRES_PASSWORD="$ADMIN_PASSWORD" -e POSTGRES_DB="$PG_DB" \
    -p 127.0.0.1::5432 "$PG_IMAGE")
  trap 'docker rm -f "$CONTAINER" >/dev/null' EXIT
  CONTRACT_PG_HOSTPORT=$(docker port "$CONTAINER" 5432/tcp | head -1)
  # The image's init server listens on the socket only, so TCP readiness means the
  # real server is up.
  for _ in $(seq 60); do
    docker exec "$CONTAINER" pg_isready -q -h 127.0.0.1 -U postgres && break
    sleep 1
  done
fi

urlquote() { python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }
ADMIN_URL="postgresql://postgres:$(urlquote "$ADMIN_PASSWORD")@$CONTRACT_PG_HOSTPORT/$PG_DB"
ORCH_URL="postgresql://$ORCH_USER:$(urlquote "$ORCH_PASSWORD")@$CONTRACT_PG_HOSTPORT/$PG_DB"
echo "Postgres at $CONTRACT_PG_HOSTPORT"

# The app's test config, pointed at this Postgres (env overrides config keys).
app() {
  (cd "$ROOT/servicex_app" && \
    APP_CONFIG_FILE="$ROOT/servicex_app/servicex_app_test/test.config" \
    SQLALCHEMY_DATABASE_URI="$ADMIN_URL" \
    ALLOWED_IMAGE_PREFIXES='["sslhep/"]' \
    FLASK_APP=servicex_app/app.py \
    poetry run "$@")
}

echo "--- migrate to v1_9_0 and seed files"
app flask db upgrade v1_9_0
app python "$SCRIPTS/check_file_key_backfill.py" seed "$ADMIN_URL"
echo "--- upgrade, downgrade, upgrade"
app flask db upgrade
app flask db downgrade v1_9_0
app flask db upgrade
app python "$SCRIPTS/check_file_key_backfill.py" check "$ADMIN_URL"

echo "--- orchestrator role (twice)"
for _ in 1 2; do
  ORCHESTRATOR_DB_USER="$ORCH_USER" ORCHESTRATOR_DB_PASSWORD="$ORCH_PASSWORD" \
    app flask orchestrator-db-role
done

echo "--- contract tests"
cd "$ROOT/servicex_orchestrator"
CONTRACT_ADMIN_URL="$ADMIN_URL" CONTRACT_ORCHESTRATOR_URL="$ORCH_URL" \
  PYTHONPATH=src poetry run pytest -m contract tests/contract "$@"
