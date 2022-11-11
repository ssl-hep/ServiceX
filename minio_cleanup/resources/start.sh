#!/bin/sh
mkdir instance
# SQLite doesn't handle migrations, so rely on SQLAlchmy table creation
PATH=.venv/bin:$PATH
. .venv/bin/activate

python3.11 ./minio_cleanup.py --max-size $MAX_SIZE --low-size $LOW_SIZE --max-age $MAX_AGE