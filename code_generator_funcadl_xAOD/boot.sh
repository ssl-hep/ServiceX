#!/bin/bash

# Running the web server?
action=${1:-web_service}
if [ "$action" = "web_service" ] ; then
    mkdir instance
    exec gunicorn -b [::]:5000 --workers=2 --threads=1 --log-level=info --access-logfile /tmp/access --error-logfile /tmp/error "xaod_code_generator:create_app()"
else
    echo "Unknown action '$action'"
fi
