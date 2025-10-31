#!/bin/bash

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

# Running the web server?
action=${1:-web_service}
if [ "$action" = "web_service" ] ; then
    mkdir instance
    exec gunicorn -b :5000 $RELOAD --workers=2 --threads=1 --access-logfile - --error-logfile - "servicex.TopCP_code_generator:create_app()"
else
    echo "Unknown action '$action'"
fi
