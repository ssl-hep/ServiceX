import shutil
from pathlib import Path

import pytest

from fake_science import Answer, FakeScienceContainer
from transformer_sidecar.file_transformer import FileTransformer, PublishError
from transformer_sidecar.object_store_manager import ObjectStoreError
from transformer_sidecar.temporal_models import FileRef, output_object_name

REQUEST_ID = "req-1"
FILE = FileRef(
    file_id=7,
    file_key="mc23:file.root",
    replicas=[
        "https://site2/file.root",
        "davs://site3/file.root",
        "root://site1/file.root",
    ],
)


def capabilities(formats=("root-file", "parquet")):
    return {"file-formats": list(formats), "stats-parser": "UprootStats"}


@pytest.fixture(autouse=True)
def no_cache_prefix(monkeypatch):
    monkeypatch.delenv("CACHE_PREFIX", raising=False)


@pytest.fixture
def object_store(mocker):
    store = mocker.MagicMock()
    store.uploaded = {}

    def upload(bucket, object_name, path):
        store.uploaded[(bucket, object_name)] = Path(path).read_bytes()
        Path(path).unlink()

    store.upload_file.side_effect = upload
    return store


def make(
    tmp_path,
    answers,
    *,
    result_format="root-file",
    formats=None,
    destination="object-store",
    object_store=None,
    output_dir=None
):
    science = FakeScienceContainer(tmp_path / "shared" / REQUEST_ID, answers)
    transformer = FileTransformer(
        request_id=REQUEST_ID,
        shared_dir=str(tmp_path / "shared"),
        result_destination=destination,
        result_format=result_format,
        capabilities=capabilities(formats) if formats else capabilities(),
        science_container=science,
        object_store=object_store,
        output_dir=output_dir,
    )
    return transformer, science


def test_success_on_first_replica(tmp_path, object_store):
    transformer, science = make(tmp_path, [Answer()], object_store=object_store)

    outcome = transformer.transform(FILE)

    name = output_object_name(FILE.file_key, "root-file")
    assert outcome.success
    assert outcome.object_name == name
    # root replicas first, davs became https
    assert outcome.replica_used == "root://site1/file.root"
    assert outcome.events == 42
    assert outcome.bytes == 4
    assert object_store.uploaded == {(REQUEST_ID, name): b"data"}
    assert science.confirmations == 1
    request = science.requests[0]
    assert request["downloadPath"] == "root://site1/file.root"
    assert request["result-format"] == "root-file"
    assert request["file-id"] == 7
    scratch = tmp_path / "shared" / REQUEST_ID / "scratch"
    assert Path(request["safeOutputFileName"]).parent == scratch
    # Nothing left in scratch
    assert list(scratch.iterdir()) == []


def test_falls_through_to_next_replica_with_same_name(tmp_path, object_store):
    transformer, science = make(
        tmp_path,
        [Answer(status="failure.", output=None), Answer()],
        object_store=object_store,
    )

    outcome = transformer.transform(FILE)

    assert outcome.success
    assert outcome.replica_used == "https://site2/file.root"
    assert [r["downloadPath"] for r in science.requests] == [
        "root://site1/file.root",
        "https://site2/file.root",
    ]
    # The output name doesn't depend on the replica
    names = {Path(r["safeOutputFileName"]).name for r in science.requests}
    assert len(names) == 1
    assert science.confirmations == 2


def test_every_replica_fails(tmp_path, object_store):
    bad = 'ValueError: key "lep_ptttt" does not exist'
    transformer, science = make(
        tmp_path,
        [Answer(status="failure.", output=None, log=bad)] * 3,
        object_store=object_store,
    )

    outcome = transformer.transform(FILE)

    assert not outcome.success
    assert outcome.replica_used == "root://site1/file.root"
    assert "lep_ptttt" in outcome.error_info
    assert bad in outcome.log_body
    assert science.confirmations == 3
    object_store.upload_file.assert_not_called()


def test_success_without_output_tries_next_replica(tmp_path, object_store):
    transformer, _ = make(
        tmp_path, [Answer(output=None)] * 3, object_store=object_store
    )

    outcome = transformer.transform(FILE)

    assert not outcome.success
    assert outcome.error_info == "The transformer reported success but wrote no output"


@pytest.mark.parametrize("converts", [True, False])
def test_converts_to_parquet(tmp_path, object_store, mocker, converts):
    def convert(path):
        if not converts:
            return None
        target = path.with_suffix(".parquet")
        shutil.copy(path, target)
        return target

    mocker.patch(
        "transformer_sidecar.file_transformer.convert_to_parquet", side_effect=convert
    )
    transformer, science = make(
        tmp_path,
        [Answer()] * 3,
        result_format="parquet",
        formats=["root-file"],
        object_store=object_store,
    )

    outcome = transformer.transform(FILE)

    assert science.requests[0]["result-format"] == "root-file"
    assert science.requests[0]["safeOutputFileName"].endswith(".root")
    if converts:
        name = output_object_name(FILE.file_key, "parquet")
        assert outcome.success
        assert name.endswith(".parquet")
        assert object_store.uploaded == {(REQUEST_ID, name): b"data"}
    else:
        assert not outcome.success
        assert outcome.error_info == "Sidecar format conversion failed"
        object_store.upload_file.assert_not_called()


def test_converts_to_rntuple(tmp_path, object_store, mocker):
    def convert(path):
        target = path.with_suffix(".rntuple.root")
        target.write_bytes(b"rntuple")
        return target

    mocker.patch(
        "transformer_sidecar.file_transformer.convert_to_rntuple", side_effect=convert
    )
    transformer, science = make(
        tmp_path,
        [Answer()],
        result_format="root-rntuple",
        formats=["root-file"],
        object_store=object_store,
    )

    outcome = transformer.transform(FILE)

    assert outcome.success
    assert science.requests[0]["result-format"] == "root-file"
    assert object_store.uploaded == {
        (REQUEST_ID, output_object_name(FILE.file_key, "root-rntuple")): b"rntuple"
    }


def test_native_parquet_is_not_converted(tmp_path, object_store, mocker):
    convert = mocker.patch("transformer_sidecar.file_transformer.convert_to_parquet")
    transformer, science = make(
        tmp_path, [Answer()], result_format="parquet", object_store=object_store
    )

    assert transformer.transform(FILE).success
    assert science.requests[0]["result-format"] == "parquet"
    convert.assert_not_called()


def test_object_store_error_is_publish_error(tmp_path, object_store):
    object_store.upload_file.side_effect = ObjectStoreError("boom")
    transformer, science = make(tmp_path, [Answer()], object_store=object_store)

    with pytest.raises(PublishError):
        transformer.transform(FILE)
    # The science container still got its confirmation
    assert science.confirmations == 1


def test_volume_destination_renames_into_place(tmp_path):
    output_dir = tmp_path / "posix"
    transformer, _ = make(
        tmp_path, [Answer()], destination="volume", output_dir=str(output_dir)
    )

    outcome = transformer.transform(FILE)

    assert outcome.success
    assert [p.name for p in output_dir.iterdir()] == [outcome.object_name]
    assert (output_dir / outcome.object_name).read_bytes() == b"data"


def test_volume_destination_overwrites_on_retry(tmp_path):
    output_dir = tmp_path / "posix"
    transformer, _ = make(
        tmp_path,
        [Answer(output=b"first"), Answer(output=b"second")],
        destination="volume",
        output_dir=str(output_dir),
    )

    first = transformer.transform(FILE)
    second = transformer.transform(FILE)

    assert first.object_name == second.object_name
    assert [p.name for p in output_dir.iterdir()] == [first.object_name]
    assert (output_dir / first.object_name).read_bytes() == b"second"


def test_volume_destination_write_error(tmp_path, mocker):
    output_dir = tmp_path / "posix"
    mocker.patch(
        "transformer_sidecar.file_transformer.shutil.copyfile",
        side_effect=OSError("disk full"),
    )
    transformer, _ = make(
        tmp_path, [Answer()], destination="volume", output_dir=str(output_dir)
    )

    with pytest.raises(PublishError, match="disk full"):
        transformer.transform(FILE)
    assert list(output_dir.iterdir()) == []


def test_cache_prefix(tmp_path, object_store, monkeypatch):
    monkeypatch.setenv("CACHE_PREFIX", "xcache:1094")
    transformer, science = make(tmp_path, [Answer()], object_store=object_store)

    outcome = transformer.transform(FILE)

    assert outcome.replica_used == "root://xcache:1094//root://site1/file.root"


def test_destination_settings_are_checked(tmp_path):
    with pytest.raises(ValueError):
        make(tmp_path, [], destination="object-store", object_store=None)
    with pytest.raises(ValueError):
        make(tmp_path, [], destination="volume", output_dir=None)
