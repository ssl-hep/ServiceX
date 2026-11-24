#!/usr/bin/env bash
# Dataset lookup end to end on a throwaway Postgres: the real app (Temporal mode,
# `flask run`), the real orchestrator worker and the real DIDFinderWorker from a
# ServiceX_DID_Finder_lib checkout, driven by tests/e2e against a local Temporal dev
# server. Transforms are still stubs.
#
#  1. Starts a throwaway Postgres 14 in docker, migrates it, creates the role.
#  2. Runs `pytest -m e2e tests/e2e`, which starts Temporal, the app and the finder.
#
# Needs docker and poetry envs for servicex_app, servicex_orchestrator (test group)
# and the DID finder lib (DID_FINDER_LIB_DIR, default ../ServiceX_DID_Finder_lib next
# to this repo). Not run in CI.
# Usage: servicex_orchestrator/scripts/lookup-e2e-test.sh [extra pytest args]
set -euo pipefail

# shellcheck source=throwaway-postgres.sh
source "$(dirname "$0")/throwaway-postgres.sh"

DID_FINDER_LIB_DIR=${DID_FINDER_LIB_DIR:-$(cd "$ROOT/.." && pwd)/ServiceX_DID_Finder_lib}
if [ ! -d "$DID_FINDER_LIB_DIR" ]; then
  echo "No DID finder lib at $DID_FINDER_LIB_DIR; set DID_FINDER_LIB_DIR" >&2
  exit 1
fi

echo "--- migrate and create the orchestrator role"
app flask db upgrade
create_orchestrator_role

echo "--- e2e tests"
cd "$ROOT/servicex_orchestrator"
CONTRACT_ADMIN_URL="$ADMIN_URL" CONTRACT_ORCHESTRATOR_URL="$ORCH_URL" \
  E2E_APP_DIR="$ROOT/servicex_app" DID_FINDER_LIB_DIR="$DID_FINDER_LIB_DIR" \
  PYTHONPATH=src poetry run pytest -m e2e tests/e2e "$@"
