#!/usr/bin/env bash
poetry run celery --broker="$BROKER_URL" -A servicex_did_finder_servicex worker \
                  --loglevel=info -Q did_finder_servicex \
                  --concurrency=1 --hostname=did_finder_servicex@%h
