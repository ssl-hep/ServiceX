#!/bin/sh

# Initialize reload flag
RELOAD=""

# Parse command line arguments
for arg in "$@"
do
    if [ "$arg" = "--reload" ]; then
        RELOAD="--reload"
        break
    fi
done

mkdir -p instance
# SQLite doesn't handle migrations, so rely on SQLAlchmy table creation
if grep "sqlite://" $APP_CONFIG_FILE; then
  echo "SQLLite DB, so skipping db migrations";
else
  FLASK_APP=servicex_app/app.py flask db upgrade;
fi
[ -d "/default_users" ] && python3 servicex/cli/create_default_users.py

# Python snippet to load the config Python file directly and find the RABBIT_MQ_URL value
RABBIT_MQ_URL=$(python3 -c "ns={}; exec(open('$APP_CONFIG_FILE').read(),{},ns); print(ns.get('RABBIT_MQ_URL','') or '')")

celery --broker="$RABBIT_MQ_URL" -A servicex_app.celery.server_tasks worker \
                  --loglevel=info \
                  --concurrency=5 &

exec gunicorn -b [::]:5000 $RELOAD --workers=5 --threads=1 --timeout 120 --log-level=warning --access-logfile /tmp/gunicorn.log --error-logfile - "servicex_app:create_app()"
# to log requests to stdout  --access-logfile -
