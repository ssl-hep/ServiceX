#!/bin/bash

# Running the web server?
action=${1:-web_service}
if [ "$action" = "web_service" ] ; then
    mkdir instance
    exec gunicorn -b :5000 --workers=2 --threads=1 --access-logfile - --error-logfile - "servicex.raw_uproot_code_generator:create_app()"
else
    echo "Unknown action '$action'"
fi
