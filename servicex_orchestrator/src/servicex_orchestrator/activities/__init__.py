from servicex_orchestrator.activities.health import ping
from servicex_orchestrator.activities.stubs import StubActivities
from servicex_orchestrator.config import Settings


def build_stubs(settings: Settings) -> StubActivities:
    return StubActivities(
        stub_files=settings.stub_dataset_files,
        stub_delay=settings.stub_activity_delay_seconds,
    )


def build_activities(settings: Settings) -> list:
    """Every activity the orchestrator's own queue serves."""
    return [ping, *build_stubs(settings).all()]


__all__ = ["StubActivities", "build_activities", "build_stubs", "ping"]
