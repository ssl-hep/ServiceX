"""The file and request-finishing activities against a real Postgres, as the
orchestrator's role: claim_file_batch, record_file_result, record_request_progress
and finalize_request. See conftest.py for what they need."""

import pytest
from temporalio.testing import ActivityEnvironment

from pg_seed import NEEDS_DB
from servicex_orchestrator.activities.files import FileActivities
from servicex_orchestrator.activities.request_status import RequestActivities
from servicex_orchestrator.models import (
    FILE_FAILURE,
    FILE_SUCCESS,
    LOOKUP_COMPLETE,
    REQUEST_BAD_DATASET,
    REQUEST_CANCELED,
    REQUEST_COMPLETE,
    ClaimBatchInput,
    FileResult,
    FinalizeInput,
    RecordFileResultInput,
    RequestProgressInput,
)

pytestmark = NEEDS_DB


@pytest.fixture
def files_(orchestrator):
    return FileActivities(orchestrator)


@pytest.fixture
def requests_(orchestrator):
    return RequestActivities(orchestrator)


async def run(fn, *args):
    return await ActivityEnvironment().run(fn, *args)


def _claim(dataset_id, after, up_to, limit=100):
    return ClaimBatchInput("req", dataset_id, after=after, up_to=up_to, limit=limit)


async def _raw_file(seed, dataset_id, paths, key=None) -> int:
    """A files row with exactly these paths, and a NULL file_key unless given."""
    await seed.execute(
        "INSERT INTO files (dataset_id, paths, file_key) VALUES (:d, :p, :k)",
        d=dataset_id,
        p=paths,
        k=key,
    )
    return await seed.scalar(
        "SELECT max(id) FROM files WHERE dataset_id = :d", d=dataset_id
    )


# ----- claim_file_batch -----------------------------------------------------------


async def test_claim_reads_the_range_in_id_order(files_, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    other = await seed.dataset(LOOKUP_COMPLETE)
    # Another dataset's files interleave with ours: ids are one sequence.
    ids = await seed.files(dataset_id, ["a0", "a1"])
    other_ids = await seed.files(other, ["b0"])
    ids += await seed.files(dataset_id, ["a2", "a3", "a4", "a5"])
    assert ids[1] < other_ids[0] < ids[2]

    batch = await run(files_.claim_file_batch, _claim(dataset_id, ids[0], ids[4]))
    assert [f.file_id for f in batch] == ids[1:5]
    assert [f.file_key for f in batch] == ["a1", "a2", "a3", "a4"]
    assert batch[0].replicas == ["root://se//a1"]

    limited = await run(files_.claim_file_batch, _claim(dataset_id, 0, ids[-1], 3))
    assert [f.file_id for f in limited] == ids[:3]


async def test_claim_past_the_last_file_is_empty(files_, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    ids = await seed.files(dataset_id, ["a0", "a1"])

    assert await run(files_.claim_file_batch, _claim(dataset_id, ids[-1], 0)) == []
    assert (
        await run(files_.claim_file_batch, _claim(dataset_id, ids[-1], ids[-1] + 10))
        == []
    )


async def test_claim_splits_the_replicas(files_, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    file_id = await _raw_file(
        seed, dataset_id, "root://a//f.root, root://b//f.root,", key="scope:f"
    )

    [ref] = await run(files_.claim_file_batch, _claim(dataset_id, 0, file_id))

    assert ref.replicas == ["root://a//f.root", "root://b//f.root"]
    assert ref.file_key == "scope:f"


async def test_claim_keys_a_file_without_file_key_by_its_first_replica(files_, seed):
    """A pre-migration duplicate: v1_10_0 backfilled keys from the first replica and
    left duplicates NULL, so the fallback gives it its twin's key."""
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    keyed = await _raw_file(
        seed, dataset_id, "root://a//f1.root,root://b//f1.root", key="root://a//f1.root"
    )
    duplicate = await _raw_file(seed, dataset_id, "root://a//f1.root,root://c//f1.root")

    batch = await run(files_.claim_file_batch, _claim(dataset_id, 0, duplicate))

    assert [(f.file_id, f.file_key) for f in batch] == [
        (keyed, "root://a//f1.root"),
        (duplicate, "root://a//f1.root"),
    ]
    assert batch[1].replicas == ["root://a//f1.root", "root://c//f1.root"]


# ----- record_file_result ---------------------------------------------------------


async def _results(seed, request_id):
    return await seed.rows(
        "SELECT file_id, file_path, transform_status, transform_time, "
        "total_events, total_bytes, avg_rate, s3_object_name, created_at "
        "FROM transform_result WHERE request_id = :r ORDER BY file_id",
        r=request_id,
    )


def _success(file_id, object_name="abc.parquet", seconds=2.5):
    return FileResult(
        file_id=file_id,
        status=FILE_SUCCESS,
        object_name=object_name,
        replica_used="root://se//replica-2",
        events=10_000,
        bytes=1_000_000,
        transform_seconds=seconds,
    )


async def test_record_success_is_idempotent(files_, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    [file_id] = await seed.files(dataset_id, ["a"])
    request_id = await seed.request(dataset_id, status="running")
    record = RecordFileResultInput(request_id, _success(file_id))

    await run(files_.record_file_result, record)
    [first] = await _results(seed, request_id)
    await run(files_.record_file_result, record)
    [again] = await _results(seed, request_id)

    assert tuple(first)[:8] == (
        file_id,
        "root://se//replica-2",
        FILE_SUCCESS,
        2,
        10_000,
        1_000_000,
        4_000.0,
        "abc.parquet",
    )
    assert again == first, "created_at and everything else as first written"


async def test_record_failure_then_success(files_, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    file_id = await _raw_file(
        seed, dataset_id, "root://a//f.root,root://b//f.root", key="k"
    )
    request_id = await seed.request(dataset_id, status="running")
    failure = FileResult(
        file_id=file_id,
        status=FILE_FAILURE,
        error_type="FileFailed",
        error_message="corrupt basket",
    )

    await run(files_.record_file_result, RecordFileResultInput(request_id, failure))
    [failed] = await _results(seed, request_id)
    # No replica reported: the file's first one. No time: zeros, never NULL (the
    # app's request statistics can't aggregate NULLs).
    assert tuple(failed)[:8] == (
        file_id,
        "root://a//f.root",
        FILE_FAILURE,
        0,
        0,
        0,
        0.0,
        None,
    )

    await run(
        files_.record_file_result, RecordFileResultInput(request_id, _success(file_id))
    )
    [succeeded] = await _results(seed, request_id)
    assert (succeeded.transform_status, succeeded.s3_object_name) == (
        FILE_SUCCESS,
        "abc.parquet",
    )
    assert succeeded.created_at == failed.created_at


async def test_results_are_per_request(files_, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    [file_id] = await seed.files(dataset_id, ["a"])
    first = await seed.request(dataset_id, status="running")
    second = await seed.request(dataset_id, status="running")

    for request_id in (first, second):
        await run(
            files_.record_file_result,
            RecordFileResultInput(request_id, _success(file_id)),
        )

    assert len(await _results(seed, first)) == 1
    assert len(await _results(seed, second)) == 1


# ----- record_request_progress / finalize_request ---------------------------------


async def _request(seed, request_id):
    return await seed.row(
        "SELECT status, files_completed, files_failed, total_events, total_bytes, "
        "failure_description, finish_time FROM requests WHERE request_id = :r",
        r=request_id,
    )


async def test_progress_writes_absolute_totals_that_never_go_down(requests_, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    request_id = await seed.request(dataset_id, status="running")

    later = RequestProgressInput(request_id, 10, 2, 100_000, 10_000_000)
    await run(requests_.record_request_progress, later)
    await run(requests_.record_request_progress, later)
    row = await _request(seed, request_id)
    assert tuple(row)[:5] == ("running", 10, 2, 100_000, 10_000_000)

    # An earlier batch's write landing late changes nothing.
    earlier = RequestProgressInput(request_id, 5, 0, 50_000, 5_000_000)
    await run(requests_.record_request_progress, earlier)
    assert tuple(await _request(seed, request_id))[:5] == tuple(row)[:5]


@pytest.mark.parametrize("final", ["complete", "fatal", "canceled", "bad_dataset"])
async def test_progress_leaves_finished_requests(requests_, seed, final):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    request_id = await seed.request(dataset_id, status=final)

    await run(
        requests_.record_request_progress, RequestProgressInput(request_id, 3, 1, 9, 9)
    )

    assert tuple(await _request(seed, request_id))[:5] == (final, 0, 0, None, None)


async def test_finalize_complete(requests_, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    request_id = await seed.request(dataset_id, status="running")

    await run(
        requests_.finalize_request,
        FinalizeInput(request_id, REQUEST_COMPLETE, 9, 1, None, 90_000, 9_000_000),
    )

    row = await _request(seed, request_id)
    assert tuple(row)[:6] == (REQUEST_COMPLETE, 9, 1, 90_000, 9_000_000, None)
    assert row.finish_time is not None


async def test_finalize_with_a_message_and_only_once(requests_, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    request_id = await seed.request(dataset_id, status="lookup")
    message = "dataset lookup failed: does_not_exist"

    await run(
        requests_.finalize_request,
        FinalizeInput(request_id, REQUEST_BAD_DATASET, 0, 0, message),
    )
    first = await _request(seed, request_id)
    # A retry (or anything later) leaves the finished request as it was.
    await run(
        requests_.finalize_request,
        FinalizeInput(request_id, REQUEST_CANCELED, 5, 5, "canceled by user"),
    )

    assert await _request(seed, request_id) == first
    assert tuple(first)[:6] == (REQUEST_BAD_DATASET, 0, 0, 0, 0, message)
    assert first.finish_time is not None


async def test_finalize_leaves_a_request_the_app_canceled(requests_, seed):
    dataset_id = await seed.dataset(LOOKUP_COMPLETE)
    request_id = await seed.request(dataset_id, status="canceled")

    await run(
        requests_.finalize_request,
        FinalizeInput(request_id, REQUEST_COMPLETE, 3, 0),
    )

    assert tuple(await _request(seed, request_id))[:2] == (REQUEST_CANCELED, 0)
