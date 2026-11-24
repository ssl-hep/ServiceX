#!/usr/bin/env bash
# Schema contract test: the app's migrations vs. the orchestrator's view of the schema.
#
#  1. Starts a throwaway Postgres 14 in docker (or uses CONTRACT_PG_HOSTPORT, as CI
#     does with a service container).
#  2. Migrates it with the app's Alembic migrations to v1_9_0, seeds files, then
#     upgrades to head, downgrades to v1_9_0 and upgrades again (round trip), and
#     checks the file_key backfill.
#  3. Creates the orchestrator role twice (the second run proves it is idempotent).
#  4. Runs the orchestrator's `contract` and `db` tests against it.
#
# Needs poetry envs for servicex_app and servicex_orchestrator (with the test group).
# Usage: servicex_orchestrator/scripts/schema-contract-test.sh [extra pytest args]
set -euo pipefail

# shellcheck source=throwaway-postgres.sh
source "$(dirname "$0")/throwaway-postgres.sh"

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
  create_orchestrator_role
done

echo "--- contract and DB activity tests"
cd "$ROOT/servicex_orchestrator"
CONTRACT_ADMIN_URL="$ADMIN_URL" CONTRACT_ORCHESTRATOR_URL="$ORCH_URL" \
  PYTHONPATH=src poetry run pytest -m "contract or db" tests/contract tests/db "$@"
