import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from servicex_orchestrator.models import (
        FILE_FAILED,
        FILE_FAILURE,
        FILE_SUCCESS,
        TRANSFORM_CODE_ERROR,
        BatchResult,
        FileBatchInput,
        FileRef,
        FileResult,
        RecordFileResultInput,
        TransformFileInput,
        TransformSpec,
    )
    from servicex_orchestrator.config import transform_task_queue
    from servicex_orchestrator.workflows.common import (
        error_type,
        orchestrator_activity,
    )

# Plan §5.2
TRANSFORM_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=15),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=5,
    non_retryable_error_types=[FILE_FAILED, TRANSFORM_CODE_ERROR],
)
TRANSFORM_FILE_TIMEOUT = timedelta(hours=4)
TRANSFORM_HEARTBEAT_TIMEOUT = timedelta(minutes=3)
TRANSFORM_SCHEDULE_TO_CLOSE = timedelta(hours=24)


@workflow.defn
class FileBatchWorkflow:
    """Transforms one batch of files and records each result (plan §4.3).

    Child of TransformRequestWorkflow, id `transform-<request_id>-batch-<n>`. Every
    file ends recorded as success or failure: a failure that exhausted its retries is
    still accounted for.
    """

    @workflow.run
    async def run(self, input: FileBatchInput) -> BatchResult:
        results = await asyncio.gather(
            *(self._transform(input.spec, f) for f in input.files)
        )
        batch = BatchResult(batch_number=input.batch_number)
        for r in results:
            if r.status == FILE_SUCCESS:
                batch.files_completed += 1
                batch.events += r.events
                batch.bytes += r.bytes
            else:
                batch.files_failed += 1
                if r.error_type == TRANSFORM_CODE_ERROR:
                    batch.code_errors += 1
        return batch

    async def _transform(self, spec: TransformSpec, file: FileRef) -> FileResult:
        try:
            result: FileResult = await workflow.execute_activity(
                "transform_file",
                TransformFileInput(spec=spec, file=file),
                result_type=FileResult,
                # The request's pilots poll this queue: the transformer sidecar
                # (pilot.py) in a Job, or the stub backend's in-process stub pilot.
                task_queue=transform_task_queue(spec.request_id),
                # No schedule_to_start: files wait legitimately while the pool grows.
                start_to_close_timeout=TRANSFORM_FILE_TIMEOUT,
                schedule_to_close_timeout=TRANSFORM_SCHEDULE_TO_CLOSE,
                heartbeat_timeout=TRANSFORM_HEARTBEAT_TIMEOUT,
                retry_policy=TRANSFORM_RETRY,
            )
        except ActivityError as err:
            kind, message = error_type(err)
            workflow.logger.warning(
                "File %s failed for good (%s: %s)", file.file_id, kind, message
            )
            result = FileResult(
                file_id=file.file_id,
                status=FILE_FAILURE,
                error_type=kind,
                error_message=message,
            )
        await orchestrator_activity(
            "record_file_result", RecordFileResultInput(spec.request_id, result)
        )
        return result
