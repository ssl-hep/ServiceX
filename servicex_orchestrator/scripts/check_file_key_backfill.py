"""Seed files at revision v1_9_0, or check the v1_10_0 backfill of them.

Run by schema-contract-test.sh in the app's poetry env (it has SQLAlchemy and
psycopg2):  python check_file_key_backfill.py seed|check <admin-url>
"""

import sys

from sqlalchemy import create_engine, text

# (paths, expected file_key): replicas are comma-joined; the second row duplicates
# the first one's first replica, as a retried Celery lookup would have left it.
FILES = [
    ("root://a//f1.root,root://b//f1.root", "root://a//f1.root"),
    ("root://a//f1.root,root://c//f1.root", None),
    ("root://a//f2.root", "root://a//f2.root"),
]


def seed(conn):
    dataset_id = conn.execute(
        text(
            "INSERT INTO datasets (name, last_used, last_updated, did_finder, "
            "lookup_status, stale) VALUES ('rucio://backfill:test', now(), now(), "
            "'rucio', 'complete', false) RETURNING id"
        )
    ).scalar_one()
    for paths, _ in FILES:
        conn.execute(
            text("INSERT INTO files (dataset_id, paths) VALUES (:d, :p)"),
            {"d": dataset_id, "p": paths},
        )


def check(conn):
    rows = conn.execute(
        text(
            "SELECT f.paths, f.file_key FROM files f JOIN datasets d "
            "ON d.id = f.dataset_id WHERE d.name = 'rucio://backfill:test' "
            "ORDER BY f.id"
        )
    ).all()
    got = [tuple(r) for r in rows]
    if got != FILES:
        sys.exit(f"file_key backfill wrong:\n  expected {FILES}\n  got      {got}")
    print("file_key backfill OK")


def main():
    action, url = sys.argv[1], sys.argv[2]
    with create_engine(url).begin() as conn:
        {"seed": seed, "check": check}[action](conn)


if __name__ == "__main__":
    main()
