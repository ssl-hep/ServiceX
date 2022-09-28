#!/bin/bash

# Running the web server or a utility?
action=${1:-web_service}
if [ "$action" = "web_service" ] ; then
    mkdir instance
    exec gunicorn -b :5000 --workers=2 -t 10000 --threads=1 --access-logfile - --error-logfile - "servicex.code_generator_service:create_app()"
elif [ "$action" = "translate" ]; then
    python from_text_to_zip.py "${@:2}"
else
    echo "Unknown action '$action'"
fi
