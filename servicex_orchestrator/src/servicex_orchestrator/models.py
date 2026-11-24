"""Dataclasses passed between the workflows and activities.

Temporal serializes these as JSON, so every field must be JSON-friendly. Renaming a
field changes the wire format of running workflows, so treat field names as an API.
"""

from dataclasses import dataclass, field
from typing import Optional

# Dataset lookup outcomes reported to subscribers by lookup_finished(status)
LOOKUP_COMPLETE = "complete"
LOOKUP_DOES_NOT_EXIST = "does_not_exist"
LOOKUP_BAD_NAME = "bad_name"
LOOKUP_INTERNAL_FAILURE = "internal_failure"
# The app's DatasetStatus values for a lookup that ended without files
LOOKUP_FAILURE_STATUSES = (
    LOOKUP_DOES_NOT_EXIST,
    LOOKUP_BAD_NAME,
    LOOKUP_INTERNAL_FAILURE,
)

# Error types a DID finder raises that must not be retried (plan §5.1)
DATASET_NOT_FOUND = "DatasetNotFound"
BAD_DID = "BadDID"
AUTH_FAILED = "AuthFailed"

# Raised (non-retryable) by the dataset activities when the request's dataset row is
# gone. The app never deletes datasets, so this means someone did by hand.
DATASET_MISSING = "DatasetMissing"

# Error types a transform worker raises (plan §5.2)
TRANSIENT_IO = "TransientIO"
FILE_FAILED = "FileFailed"
TRANSFORM_CODE_ERROR = "TransformCodeError"

# Request statuses, matching servicex_app.models.TransformStatus names
REQUEST_RUNNING = "running"
REQUEST_COMPLETE = "complete"
REQUEST_FATAL = "fatal"
REQUEST_BAD_DATASET = "bad_dataset"
REQUEST_CANCELED = "canceled"

FILE_SUCCESS = "success"
FILE_FAILURE = "failure"


@dataclass
class GetDatasetInput:
    request_id: str
    did_hash: str
    did: str
    did_scheme: str
    dataset_id: int


@dataclass
class DatasetInfo:
    dataset_id: int
    lookup_status: str
    n_files_known: int
    # Highest files.id in the dataset. Only meaningful once the lookup is complete.
    max_file_id: int = 0


@dataclass
class LookupInput:
    did_hash: str
    did: str
    did_scheme: str
    dataset_id: int


@dataclass
class StartLookupInput:
    lookup: LookupInput
    subscriber_workflow_id: str


@dataclass
class LookupSummary:
    n_files: int
    max_file_id: int
    size_bytes: int = 0
    events: int = 0


@dataclass
class MarkDatasetFailedInput:
    dataset_id: int
    status: str
    message: str


@dataclass
class RecordWorkflowInput:
    request_id: str
    workflow_id: str
    workflow_run_id: str


@dataclass
class MarkRequestRunningInput:
    request_id: str
    # How many files the request will transform: the dataset's file count
    files: int


@dataclass
class FileRef:
    file_id: int
    file_key: str
    replicas: list[str]


@dataclass
class ClaimBatchInput:
    request_id: str
    dataset_id: int
    after: int
    up_to: int
    limit: int


@dataclass
class TransformSpec:
    """What a transform worker needs to know about the request, besides the file."""

    request_id: str
    result_destination: str
    result_format: str


@dataclass
class FileBatchInput:
    spec: TransformSpec
    batch_number: int
    files: list[FileRef]


@dataclass
class TransformFileInput:
    spec: TransformSpec
    file: FileRef


@dataclass
class FileResult:
    file_id: int
    status: str
    object_name: Optional[str] = None
    replica_used: Optional[str] = None
    events: int = 0
    bytes: int = 0
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    # Wall time the transform took; 0 when unknown (e.g. a file that failed for good)
    transform_seconds: float = 0.0


@dataclass
class RecordFileResultInput:
    request_id: str
    result: FileResult


@dataclass
class BatchResult:
    batch_number: int
    files_completed: int = 0
    files_failed: int = 0
    code_errors: int = 0
    # Summed over the batch's successful files
    events: int = 0
    bytes: int = 0


@dataclass
class RequestProgressInput:
    """The request's running totals, as absolute values the workflow holds."""

    request_id: str
    files_completed: int
    files_failed: int
    total_events: int = 0
    total_bytes: int = 0


@dataclass
class FinalizeInput:
    request_id: str
    status: str
    files_completed: int
    files_failed: int
    message: Optional[str] = None
    total_events: int = 0
    total_bytes: int = 0


@dataclass
class PoolSpec:
    """Everything needed to build a transformer pilot (Job) for the request."""

    request_id: str
    image: str
    generated_code_cm: str
    transformer_language: str
    transformer_command: str
    result_destination: str
    result_format: str


@dataclass
class PoolState:
    """Carried across PoolManagerWorkflow continue-as-new."""

    outstanding: int = 0
    generation: int = 0
    # Sequence number of the last backlog signal applied, so a stale one is ignored
    backlog_seq: int = 0


@dataclass
class PoolInput:
    spec: PoolSpec
    max_workers: int
    reconcile_seconds: float = 30.0
    max_iterations: int = 500
    state: PoolState = field(default_factory=PoolState)


@dataclass
class LaunchPilotsInput:
    spec: PoolSpec
    count: int
    generation: int


@dataclass
class TransformRequestState:
    """Carried across TransformRequestWorkflow continue-as-new."""

    initialized: bool = False
    dataset_id: int = 0
    cursor: int = 0
    hwm: int = 0
    lookup_status: Optional[str] = None
    pool_started: bool = False
    # Set once the request's file count is recorded (mark_request_running), or
    # known to be zero, so it is done once across continue-as-new
    files_recorded: bool = False
    backlog_seq: int = 0
    batches_started: int = 0
    files_dispatched: int = 0
    files_completed: int = 0
    files_failed: int = 0
    total_events: int = 0
    total_bytes: int = 0


@dataclass
class TransformRequestTuning:
    """Knobs for TransformRequestWorkflow. Tests shrink them to hit edge cases."""

    batch_size: int = 500
    max_concurrent_batches: int = 4
    batches_per_run: int = 50
    pool_reconcile_seconds: float = 30.0


@dataclass
class TransformRequestStatus:
    """Answer to the `status` query. For debugging; the DB stays the source of truth."""

    dataset_id: int
    cursor: int
    hwm: int
    lookup_status: Optional[str]
    batches_in_flight: int
    files_dispatched: int
    files_completed: int
    files_failed: int


@dataclass
class TransformRequestResult:
    request_id: str
    status: str
    files_completed: int
    files_failed: int


@dataclass
class TransformRequestInput:
    """Input of TransformRequestWorkflow.

    The ServiceX app sends this as a plain JSON object without importing this package
    (`servicex_app/temporal_adaptor.py`), so the field names are a contract with it.

    `tuning` and `state` are internal: the app leaves them out. Workflow arguments
    are decoded by type only when their count matches the run() signature, so they
    ride in this one argument rather than as extra parameters.
    """

    request_id: str
    did: str
    did_scheme: str
    dataset_id: int
    image: str
    generated_code_cm: str
    transformer_language: str
    transformer_command: str
    result_destination: str
    result_format: str
    max_workers: int
    tuning: TransformRequestTuning = field(default_factory=TransformRequestTuning)
    # Set only when the workflow continues as new
    state: Optional[TransformRequestState] = None
