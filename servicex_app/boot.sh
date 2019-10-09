#!/bin/sh
mkdir instance
#flask db upgrade
#flask translate compile
exec gunicorn -b :5000 --workers=10 --threads=2 --access-logfile - --error-logfile - "servicex:create_app()"
