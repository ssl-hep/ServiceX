from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from servicex_orchestrator.activities.health import ping
from servicex_orchestrator.activities.stubs import StubActivities
from servicex_orchestrator.config import Settings


def build_stubs(settings: Settings) -> StubActivities:
    return StubActivities(
        stub_files=settings.stub_dataset_files,
        stub_delay=settings.stub_activity_delay_seconds,
    )


def build_activities(settings: Settings, engine: Optional[AsyncEngine] = None) -> list:
    """Every activity the orchestrator's own queue serves.

    `engine` is the ServiceX Postgres pool, for the DB activities that replace the
    stubs. None when DATABASE_URL is unset; nothing uses it yet.
    """
    return [ping, *build_stubs(settings).all()]


__all__ = ["StubActivities", "build_activities", "build_stubs", "ping"]
