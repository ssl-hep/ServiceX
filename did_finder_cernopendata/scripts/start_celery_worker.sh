#!/usr/bin/env bash
poetry run celery --broker="$BROKER_URL" -A did_finder_cernopendata worker \
                  --loglevel=info -Q did_finder_cernopendata \
                  --concurrency=1 --hostname=did_finder_cernopendata@%h
