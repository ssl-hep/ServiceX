#!/bin/sh
mkdir instance
# SQLite doesn't handle migrations, so rely on SQLAlchmy table creation
if grep "sqlite://" $APP_CONFIG_FILE; then
  echo "SQLLite DB, so skipping db migrations";
else
  FLASK_APP=servicex/app.py flask db upgrade;
fi
[ -d "/default_users" ] && python3 servicex/cli/create_default_users.py
exec gunicorn -b :5000 --workers=5 --threads=1 --timeout 120 --log-level=warning --access-logfile /tmp/gunicorn.log --error-logfile - "servicex:create_app()"
# to log requests to stdout  --access-logfile -