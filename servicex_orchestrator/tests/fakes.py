"""In-memory stand-ins for the orchestrator's DB activities, for workflow tests that
run without Postgres (tests/db/ runs the real ones)."""

from collections import defaultdict
from typing import Optional

from temporalio import activity
from temporalio.exceptions import ApplicationError

from servicex_orchestrator.models import (
    DATASET_MISSING,
    LOOKUP_COMPLETE,
    DatasetInfo,
    GetDatasetInput,
    LookupSummary,
    MarkDatasetFailedInput,
    MarkRequestRunningInput,
    RecordWorkflowInput,
)


class FakeDatabase:
    """Dataset rows and request bookkeeping kept in a dict.

    A dataset id that was never preset reads as `looking` with no files, the way
    submit leaves a new dataset. `calls` records every call by activity name.
    """

    def __init__(self, calls: Optional[dict] = None):
        self.datasets: dict[int, DatasetInfo] = {}
        self.missing: set[int] = set()
        self.calls: dict[str, list] = calls if calls is not None else defaultdict(list)

    def preset(self, dataset_id: int, status: str, n_files: int = 0) -> None:
        self.datasets[dataset_id] = DatasetInfo(
            dataset_id, status, n_files_known=n_files, max_file_id=n_files
        )

    def _read(self, dataset_id: int) -> DatasetInfo:
        if dataset_id in self.missing:
            raise ApplicationError("gone", type=DATASET_MISSING, non_retryable=True)
        return self.datasets.setdefault(
            dataset_id, DatasetInfo(dataset_id, "looking", n_files_known=0)
        )

    @activity.defn
    async def get_or_create_dataset(self, input: GetDatasetInput) -> DatasetInfo:
        self.calls["get_or_create_dataset"].append(input)
        return self._read(input.dataset_id)

    @activity.defn
    async def read_dataset(self, dataset_id: int) -> DatasetInfo:
        self.calls["read_dataset"].append(dataset_id)
        return self._read(dataset_id)

    @activity.defn
    async def mark_dataset_looking(self, dataset_id: int) -> None:
        self.calls["mark_dataset_looking"].append(dataset_id)
        info = self._read(dataset_id)
        if info.lookup_status != LOOKUP_COMPLETE:
            info.lookup_status = "looking"

    @activity.defn
    async def mark_dataset_complete(
        self, dataset_id: int, summary: LookupSummary
    ) -> None:
        self.calls["mark_dataset_complete"].append((dataset_id, summary))
        self.datasets[dataset_id] = DatasetInfo(
            dataset_id,
            LOOKUP_COMPLETE,
            n_files_known=summary.n_files,
            max_file_id=summary.max_file_id,
        )

    @activity.defn
    async def mark_dataset_failed(self, input: MarkDatasetFailedInput) -> None:
        self.calls["mark_dataset_failed"].append(input)
        self._read(input.dataset_id).lookup_status = input.status

    @activity.defn
    async def record_request_workflow(self, input: RecordWorkflowInput) -> None:
        self.calls["record_request_workflow"].append(input)

    @activity.defn
    async def mark_request_running(self, input: MarkRequestRunningInput) -> None:
        self.calls["mark_request_running"].append(input)

    def all(self) -> list:
        return [
            self.get_or_create_dataset,
            self.read_dataset,
            self.mark_dataset_looking,
            self.mark_dataset_complete,
            self.mark_dataset_failed,
            self.record_request_workflow,
            self.mark_request_running,
        ]
