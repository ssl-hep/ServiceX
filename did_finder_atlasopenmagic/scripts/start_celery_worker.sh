#!/usr/bin/env bash
poetry run celery --broker="$BROKER_URL" -A did_finder_atlasopenmagic worker \
                  --loglevel=info -Q did_finder_atlasopenmagic \
                  --concurrency=1 --hostname=did_finder_atlasopenmagic@%h
