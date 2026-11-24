# Sourced by schema-contract-test.sh and lookup-e2e-test.sh: a throwaway Postgres 14
# in docker (or CONTRACT_PG_HOSTPORT, as CI does with a service container), and
# helpers to run the app against it.
#
# Defines ROOT, SCRIPTS, ADMIN_URL, ORCH_URL, ORCH_USER, ORCH_PASSWORD, and:
#   app <cmd...>            run <cmd> in servicex_app's poetry env, configured for it
#   create_orchestrator_role
# The container is removed on exit.

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
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

create_orchestrator_role() {
  ORCHESTRATOR_DB_USER="$ORCH_USER" ORCHESTRATOR_DB_PASSWORD="$ORCH_PASSWORD" \
    app flask orchestrator-db-role
}
