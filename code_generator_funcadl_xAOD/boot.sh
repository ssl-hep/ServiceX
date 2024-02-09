#!/bin/bash

# Running the web server or a utility?
action=${1:-web_service}
if [ "$action" = "web_service" ] ; then
    mkdir instance
    exec gunicorn -b :5000 --workers=2 --threads=1 --log-level=info --access-logfile /tmp/access --error-logfile /tmp/error "xaod_code_generator:create_app()"
elif [ "$action" = "translate" ]; then
    python from_ast_to_zip.py "${@:2}"
else
    echo "Unknown action '$action'"
fi
