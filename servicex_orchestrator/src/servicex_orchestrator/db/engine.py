"""The orchestrator's connection pool to the ServiceX Postgres."""

import asyncio
import logging

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from servicex_orchestrator.config import Settings
from servicex_orchestrator.db.schema_check import (
    SchemaMismatch,
    check_schema,
    schema_revision,
)

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 10
STARTUP_CHECK_TIMEOUT_SECONDS = 30


class DatabaseUnavailable(Exception):
    pass


def async_url(database_url: str) -> URL:
    """The URL with the asyncpg driver, whatever driver (if any) it named."""
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError(
            f"DATABASE_URL must be a PostgreSQL URL, not {url.get_backend_name()}"
        )
    return url.set(drivername="postgresql+asyncpg")


def create_engine(settings: Settings) -> AsyncEngine:
    """One small pool per orchestrator replica (DB_POOL_SIZE + DB_MAX_OVERFLOW)."""
    if not settings.database_url:
        raise ValueError("DATABASE_URL is not set")
    return create_async_engine(
        async_url(settings.database_url),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        connect_args={"timeout": CONNECT_TIMEOUT_SECONDS},
    )


def describe(engine: AsyncEngine) -> str:
    """Where the engine points, without the password."""
    url = engine.url
    return f"{url.username}@{url.host}:{url.port or 5432}/{url.database}"


async def startup_check(engine: AsyncEngine) -> str:
    """Connect once and check the schema and grants; return the alembic revision.

    Raises DatabaseUnavailable or SchemaMismatch with a message fit for the log.
    """
    try:
        async with asyncio.timeout(STARTUP_CHECK_TIMEOUT_SECONDS):
            async with engine.connect() as conn:
                revision = await schema_revision(conn)
                problems = await check_schema(conn)
    except (OSError, TimeoutError) as err:
        raise DatabaseUnavailable(
            f"Can't reach Postgres at {describe(engine)}: {err!r}"
        ) from err
    except Exception as err:
        # asyncpg and SQLAlchemy errors: authentication, missing database, ...
        raise DatabaseUnavailable(
            f"Can't use Postgres at {describe(engine)}: {err}"
        ) from err
    if problems:
        raise SchemaMismatch(revision, problems)
    return revision or "unknown"
