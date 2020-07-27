#!/bin/sh
mkdir instance
FLASK_APP=servicex/app.py flask db upgrade
#flask db upgrade
#flask translate compile
exec gunicorn -b :5000 --workers=5 --threads=1 --timeout 120 --access-logfile - --error-logfile - "servicex:create_app()"
