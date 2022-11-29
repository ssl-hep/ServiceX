#!/bin/sh
PATH=.venv/bin:$PATH
. .venv/bin/activate
env
python3.11 ./minio_cleanup.py --max-size $MAX_SIZE --norm-size $NORM_SIZE --max-age $MAX_AGE