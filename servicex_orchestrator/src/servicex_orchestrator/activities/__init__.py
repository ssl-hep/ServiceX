from servicex_orchestrator.activities.health import ping
from servicex_orchestrator.activities.stubs import StubActivities
from servicex_orchestrator.config import Settings


def build_activities(settings: Settings) -> list:
    """Every activity the orchestrator worker registers."""
    stubs = StubActivities(
        stub_files=settings.stub_dataset_files,
        stub_delay=settings.stub_activity_delay_seconds,
    )
    return [ping, *stubs.all()]


__all__ = ["StubActivities", "build_activities", "ping"]
