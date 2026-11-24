"""Fixtures for tests that run the orchestrator's DB activities on a real Postgres.
Without CONTRACT_ADMIN_URL and CONTRACT_ORCHESTRATOR_URL every test here is skipped
(see pg_seed.NEEDS_DB)."""

import pytest

from pg_seed import ADMIN_URL, ORCHESTRATOR_URL, Seeder, engine


@pytest.fixture
async def admin():
    admin_engine = engine(ADMIN_URL)
    yield admin_engine
    await admin_engine.dispose()


@pytest.fixture
async def orchestrator():
    """The orchestrator's own role, as the activities run in production."""
    orchestrator_engine = engine(ORCHESTRATOR_URL)
    yield orchestrator_engine
    await orchestrator_engine.dispose()


@pytest.fixture
async def seed(admin):
    seeder = Seeder(admin)
    yield seeder
    await seeder.cleanup()
