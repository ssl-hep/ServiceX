from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from servicex_orchestrator.activities.datasets import DatasetActivities
from servicex_orchestrator.activities.health import ping
from servicex_orchestrator.activities.request_status import RequestActivities
from servicex_orchestrator.activities.stubs import StubActivities
from servicex_orchestrator.config import Settings


def build_stubs(settings: Settings) -> StubActivities:
    return StubActivities(
        stub_files=settings.stub_dataset_files,
        stub_delay=settings.stub_activity_delay_seconds,
    )


def build_db_activities(engine: AsyncEngine) -> list:
    """The activities that read and write the ServiceX Postgres."""
    return [*DatasetActivities(engine).all(), *RequestActivities(engine).all()]


def build_activities(
    settings: Settings,
    engine: Optional[AsyncEngine] = None,
    *,
    db_activities: Optional[list] = None,
) -> list:
    """Every activity the orchestrator's own queue serves.

    The DB activities are built on `engine` (the ServiceX Postgres pool) unless
    `db_activities` is given, as tests do with in-memory fakes.
    """
    if db_activities is None:
        if engine is None:
            raise ValueError("build_activities needs a database engine")
        db_activities = build_db_activities(engine)
    return [ping, *db_activities, *build_stubs(settings).all()]


__all__ = [
    "DatasetActivities",
    "RequestActivities",
    "StubActivities",
    "build_activities",
    "build_db_activities",
    "build_stubs",
    "ping",
]
