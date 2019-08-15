#!/bin/sh
#flask db upgrade
#flask translate compile
exec gunicorn -b :5000 --workers=5 --threads=2 --access-logfile - --error-logfile - run:app
