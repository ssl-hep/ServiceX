#!/usr/bin/env bash
poetry run celery --broker="$BROKER_URL" -A servicex_did_finder_xrootd worker \
                  --loglevel=info -Q did_finder_xrootd \
                  --concurrency=1 --hostname=did_finder_xrootd@%h
