#!/bin/sh
mkdir instance
exec gunicorn -b :5000 --workers=2 --threads=1 --access-logfile - --error-logfile - "servicex.code_generator_service:create_app()"
