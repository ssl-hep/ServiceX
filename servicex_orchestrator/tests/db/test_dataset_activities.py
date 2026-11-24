"""The dataset and request activities against a real Postgres, as the orchestrator's
role. See conftest.py for what they need."""

import pytest
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from pg_seed import NEEDS_DB
from servicex_orchestrator.activities.datasets import DatasetActivities
from servicex_orchestrator.activities.request_status import RequestActivities
from servicex_orchestrator.models import (
    DATASET_MISSING,
    LOOKUP_COMPLETE,
    LOOKUP_FAILURE_STATUSES,
    GetDatasetInput,
    LookupSummary,
    MarkDatasetFailedInput,
    MarkRequestRunningInput,
    RecordWorkflowInput,
)

pytestmark = NEEDS_DB

MISSING_ID = 2_000_000_000


@pytest.fixture
def datasets(orchestrator):
    return DatasetActivities(orchestrator)


@pytest.fixture
def requests_(orchestrator):
    return RequestActivities(orchestrator)


async def run(fn, *args):
    return await ActivityEnvironment().run(fn, *args)


def _get(dataset_id, scheme="rucio"):
    return GetDatasetInput("req", "hash", f"{scheme}://some", scheme, dataset_id)


# ----- get_or_create_dataset / read_dataset ---------------------------------------


async def test_complete_dataset_is_a_cache_hit(datasets, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    ids = await seed.files(dataset_id, ["a", "b", "c"])

    info = await run(datasets.get_or_create_dataset, _get(dataset_id))

    assert info.lookup_status == LOOKUP_COMPLETE
    assert (info.n_files_known, info.max_file_id) == (3, max(ids))


async def test_dataset_being_looked_up(datasets, seed):
    dataset_id = await seed.dataset("looking")
    await seed.files(dataset_id, ["a"])

    info = await run(datasets.read_dataset, dataset_id)

    assert (info.lookup_status, info.n_files_known) == ("looking", 1)


async def test_empty_dataset_reports_zero(datasets, seed):
    dataset_id = await seed.dataset("created")
    info = await run(datasets.read_dataset, dataset_id)
    assert (info.n_files_known, info.max_file_id) == (0, 0)


async def test_user_file_list_dataset_is_complete(datasets, seed):
    """The app creates a file-list dataset complete, with its files."""
    dataset_id = await seed.dataset(LOOKUP_COMPLETE, did_finder="user")
    await seed.files(dataset_id, ["root://x/1.root", "root://x/2.root"])

    info = await run(datasets.get_or_create_dataset, _get(dataset_id, "user"))

    assert (info.lookup_status, info.n_files_known) == (LOOKUP_COMPLETE, 2)


async def test_stale_dataset_is_used_as_it_is(datasets, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE, stale=True)
    await seed.files(dataset_id, ["a", "b"])

    info = await run(datasets.get_or_create_dataset, _get(dataset_id))

    assert (info.lookup_status, info.n_files_known) == (LOOKUP_COMPLETE, 2)


async def test_missing_dataset_is_not_retried(datasets):
    with pytest.raises(ApplicationError) as err:
        await run(datasets.get_or_create_dataset, _get(MISSING_ID))
    assert err.value.type == DATASET_MISSING
    assert err.value.non_retryable


# ----- mark_dataset_* -------------------------------------------------------------


async def test_mark_looking(datasets, seed):
    dataset_id = await seed.dataset("created")
    await run(datasets.mark_dataset_looking, dataset_id)
    await run(datasets.mark_dataset_looking, dataset_id)
    status = await seed.scalar(
        "SELECT lookup_status FROM datasets WHERE id = :d", d=dataset_id
    )
    assert status == "looking"


async def test_mark_looking_never_uncompletes(datasets, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    await run(datasets.mark_dataset_looking, dataset_id)
    status = await seed.scalar(
        "SELECT lookup_status FROM datasets WHERE id = :d", d=dataset_id
    )
    assert status == LOOKUP_COMPLETE


async def test_mark_complete_counts_the_files_and_is_idempotent(datasets, seed):
    dataset_id = await seed.dataset("looking")
    await seed.files(dataset_id, ["a", "b", "c"], size=1000, events=10)
    # The summary of a retried attempt that saw only part of the dataset.
    summary = LookupSummary(n_files=1, max_file_id=0, size_bytes=1000, events=10)

    for _ in range(2):
        await run(datasets.mark_dataset_complete, dataset_id, summary)

    row = await seed.row(
        "SELECT lookup_status, n_files, size, events, last_updated "
        "FROM datasets WHERE id = :d",
        d=dataset_id,
    )
    assert (row.lookup_status, row.n_files, row.size, row.events) == (
        LOOKUP_COMPLETE,
        3,
        3000,
        30,
    )
    assert row.last_updated is not None


async def test_mark_complete_with_no_files(datasets, seed):
    dataset_id = await seed.dataset("looking")
    await run(datasets.mark_dataset_complete, dataset_id, LookupSummary(0, 0))
    row = await seed.row(
        "SELECT lookup_status, n_files, size, events FROM datasets WHERE id = :d",
        d=dataset_id,
    )
    assert tuple(row) == (LOOKUP_COMPLETE, 0, 0, 0)


@pytest.mark.parametrize("status", LOOKUP_FAILURE_STATUSES)
async def test_mark_failed(datasets, seed, status):
    dataset_id = await seed.dataset("looking")
    failure = MarkDatasetFailedInput(dataset_id, status, "DatasetNotFound: nope")
    await run(datasets.mark_dataset_failed, failure)
    await run(datasets.mark_dataset_failed, failure)
    assert (
        await seed.scalar(
            "SELECT lookup_status FROM datasets WHERE id = :d", d=dataset_id
        )
        == status
    )


async def test_mark_failed_rejects_other_statuses(datasets, seed):
    dataset_id = await seed.dataset("looking")
    with pytest.raises(ApplicationError) as err:
        await run(
            datasets.mark_dataset_failed,
            MarkDatasetFailedInput(dataset_id, "failed", "x"),
        )
    assert err.value.non_retryable


# ----- request bookkeeping --------------------------------------------------------


async def test_record_request_workflow(requests_, seed):
    request_id = await seed.request(await seed.dataset())
    record = RecordWorkflowInput(request_id, f"transform-{request_id}", "run-1")
    await run(requests_.record_request_workflow, record)
    await run(requests_.record_request_workflow, record)
    row = await seed.row(
        "SELECT workflow_id, workflow_run_id FROM requests WHERE request_id = :r",
        r=request_id,
    )
    assert tuple(row) == (f"transform-{request_id}", "run-1")


@pytest.mark.parametrize("before", ["submitted", "pending_lookup", "lookup", "running"])
async def test_mark_request_running(requests_, seed, before):
    request_id = await seed.request(await seed.dataset(), status=before)
    running = MarkRequestRunningInput(request_id, 17)
    await run(requests_.mark_request_running, running)
    await run(requests_.mark_request_running, running)
    row = await seed.row(
        "SELECT status, files FROM requests WHERE request_id = :r", r=request_id
    )
    assert tuple(row) == ("running", 17)


@pytest.mark.parametrize("final", ["complete", "fatal", "canceled", "bad_dataset"])
async def test_mark_request_running_leaves_finished_requests(requests_, seed, final):
    request_id = await seed.request(await seed.dataset(), status=final)
    await run(requests_.mark_request_running, MarkRequestRunningInput(request_id, 17))
    row = await seed.row(
        "SELECT status, files FROM requests WHERE request_id = :r", r=request_id
    )
    assert tuple(row) == (final, 0)
