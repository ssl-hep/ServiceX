from servicex_orchestrator.workflows.dataset_lookup import DatasetLookupWorkflow
from servicex_orchestrator.workflows.file_batch import FileBatchWorkflow
from servicex_orchestrator.workflows.ping import PingWorkflow
from servicex_orchestrator.workflows.pool_manager import PoolManagerWorkflow
from servicex_orchestrator.workflows.transform_request import TransformRequestWorkflow

WORKFLOWS = [
    PingWorkflow,
    TransformRequestWorkflow,
    DatasetLookupWorkflow,
    FileBatchWorkflow,
    PoolManagerWorkflow,
]

__all__ = [
    "WORKFLOWS",
    "DatasetLookupWorkflow",
    "FileBatchWorkflow",
    "PingWorkflow",
    "PoolManagerWorkflow",
    "TransformRequestWorkflow",
]
