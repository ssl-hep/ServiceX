import hashlib

from temporalio.converter import DataConverter

from transformer_sidecar.temporal_models import (
    FileRef,
    FileResult,
    TransformFileInput,
    TransformSpec,
    output_object_name,
)


def test_output_object_name():
    key = "mc23_13p6TeV:DAOD_PHYSLITE.12345._000001.pool.root.1"
    digest = hashlib.sha256(key.encode()).hexdigest()[:40]
    assert output_object_name(key, "parquet") == digest + ".parquet"
    assert output_object_name(key, "root-file") == digest + ".root"
    assert output_object_name(key, "root-rntuple") == digest + ".root"


def test_input_decodes_orchestrator_json():
    """The JSON the orchestrator sends: field names are the contract."""
    payload = DataConverter.default.payload_converter.to_payloads(
        [
            {
                "spec": {
                    "request_id": "r1",
                    "result_destination": "object-store",
                    "result_format": "parquet",
                },
                "file": {"file_id": 3, "file_key": "k", "replicas": ["root://a"]},
            }
        ]
    )
    [decoded] = DataConverter.default.payload_converter.from_payloads(
        payload, [TransformFileInput]
    )
    assert decoded == TransformFileInput(
        spec=TransformSpec("r1", "object-store", "parquet"),
        file=FileRef(3, "k", ["root://a"]),
    )


def test_result_encodes_orchestrator_fields():
    payload = DataConverter.default.payload_converter.to_payloads(
        [FileResult(file_id=3, status="success", object_name="o", events=5)]
    )
    [decoded] = DataConverter.default.payload_converter.from_payloads(payload, [dict])
    assert set(decoded) == {
        "file_id",
        "status",
        "object_name",
        "replica_used",
        "events",
        "bytes",
        "error_type",
        "error_message",
        "transform_seconds",
    }
