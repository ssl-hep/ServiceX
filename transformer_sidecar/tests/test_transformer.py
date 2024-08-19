# Copyright (c) 2024, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
import contextlib
import json
import os
import random
import signal
import tempfile
from pathlib import PosixPath
from types import SimpleNamespace

from pytest import fixture

from transformer_sidecar.transformer import init, transform_file, prioritize_replicas, \
    prepend_xcache

# Test data
test_request_id = "test-request-123"
test_file_id = "file-456"
test_paths = ["site1:file.root", "site2:file.root"]
test_service_endpoint = "https://test-service.example.com/transform"
test_result_destination = "s3://test-bucket/results/"
test_result_format = "json"


@fixture
def transformer_capabilities():
    return {
        "name": "Uproot transformer using native uproot arguments",
        "description": "Extracts data from flat ntuple style root files.",
        "limitations": "Would be good to note what isn't implemented",
        "file-formats": ['root'],
        "stats-parser": "UprootStats",
        "language": "python",
        "command": "/generated/transform_single_file.py"
    }


def save_transformer_capabilities(temp_dir, transformer_capabilities):
    with open(os.path.join(temp_dir, 'transformer_capabilities.json'), 'w') as f:
        json.dump(transformer_capabilities, f)


@fixture
def mock_celery(monkeypatch, mocker):
    mock_app = mocker.MagicMock()
    monkeypatch.setattr('celery.Celery', lambda *args, **kwargs: mock_app)
    return mock_app


@fixture
def mock_object_store_manager(mocker):
    return mocker.patch('transformer_sidecar.transformer.ObjectStoreManager')


@fixture
def mock_object_store_uploader(mocker):
    return mocker.patch('transformer_sidecar.transformer.ObjectStoreUploader')


@fixture
def mock_science_container(mocker):
    return mocker.patch('transformer_sidecar.transformer.ScienceContainerCommand')


@fixture
def mock_input_queue(mocker):
    return mocker.patch("transformer_sidecar.transformer.Queue")


@fixture
def mock_servicex_adapter(mocker):
    return mocker.patch('transformer_sidecar.transformer.ServiceXAdapter')


@fixture
def args():
    return SimpleNamespace(
        request_id='1234',
        shared_dir='/shared',
        output_dir=None,
        rabbit_uri='amqp://localhost',
        result_destination='object-store',
        result_format='root',
    )


def init_test(args, mock_celery, transformer_capabilities,
              temp_dir, file_formats: list[str], result_format: str):
    args.shared_dir = temp_dir

    transformer_capabilities['file-formats'] = file_formats
    args.result_format = result_format

    save_transformer_capabilities(temp_dir, transformer_capabilities)

    init(args=args, app=mock_celery)
    scripts_dir = os.path.join(temp_dir, "scripts")
    assert os.path.isdir(scripts_dir)
    assert os.path.isfile(os.path.join(scripts_dir, 'watch.sh'))
    assert os.path.isfile(os.path.join(scripts_dir, 'proxy-exporter.sh'))


def test_transformer_init(args, mock_celery, transformer_capabilities,
                          mock_object_store_uploader, mock_object_store_manager,
                          mock_science_container):
    with (tempfile.TemporaryDirectory() as temp_dir):
        init_test(args, mock_celery, transformer_capabilities, temp_dir,
                  ['root', 'parquet'], 'root')

        mock_object_store_uploader.assert_called_once()
        object_store_uploader_args = mock_object_store_uploader.call_args.kwargs
        assert object_store_uploader_args["request_id"] == '1234'
        assert object_store_uploader_args["convert_root_to_parquet"] is False

        mock_science_container.assert_called_once()
        mock_celery.worker_main.assert_called_with(
            argv=[
                "worker",
                "--concurrency=1",
                '--without-mingle',
                '--without-gossip',
                '--without-heartbeat',
                "--loglevel=info",
                '-Q', 'transformer-1234',
                "-n", "transformer-1234@%h",
            ]
        )


def test_transformer_root_to_parquet(args, mock_celery, transformer_capabilities,
                                     mock_servicex_adapter,
                                     mock_object_store_uploader, mock_input_queue,
                                     mock_object_store_manager,
                                     mock_science_container):
    with (tempfile.TemporaryDirectory() as temp_dir):
        init_test(args, mock_celery, transformer_capabilities, temp_dir,
                  ['root'], 'parquet')

        object_store_uploader_args = mock_object_store_uploader.call_args.kwargs
        assert object_store_uploader_args["request_id"] == '1234'
        assert object_store_uploader_args["convert_root_to_parquet"] is True

        mock_science_container.return_value.await_response.side_effect = ["failure",
                                                                          "success."]

        # Call the task
        transform_file(
            request_id=test_request_id,
            file_id=test_file_id,
            paths=test_paths,
            service_endpoint=test_service_endpoint,
            result_destination=test_result_destination,
            result_format="parquet"
        )

        science_request = mock_science_container.return_value.send.call_args[0][0]
        assert science_request["result-format"] == "root"


def test_transformer_parquet(args, mock_celery, transformer_capabilities,
                             mock_servicex_adapter,
                             mock_object_store_uploader, mock_input_queue,
                             mock_object_store_manager,
                             mock_science_container):
    with (tempfile.TemporaryDirectory() as temp_dir):
        init_test(args, mock_celery, transformer_capabilities, temp_dir,
                  ['root', 'parquet'], 'parquet')

        object_store_uploader_args = mock_object_store_uploader.call_args.kwargs
        assert object_store_uploader_args["request_id"] == '1234'
        assert object_store_uploader_args["convert_root_to_parquet"] is False

        mock_science_container.return_value.await_response.side_effect = ["failure",
                                                                          "success."]

        # Call the task
        transform_file(
            request_id=test_request_id,
            file_id=test_file_id,
            paths=test_paths,
            service_endpoint=test_service_endpoint,
            result_destination=test_result_destination,
            result_format="parquet"
        )

        science_request = mock_science_container.return_value.send.call_args[0][0]
        assert science_request["result-format"] == "parquet"


def test_transformer_output_dir(args, mock_celery, transformer_capabilities,
                                mock_servicex_adapter,
                                mock_science_container, mocker):
    with (tempfile.TemporaryDirectory() as temp_dir):
        args.result_destination = 'volume'
        args.output_dir = "/local/results"

        init_test(args, mock_celery, transformer_capabilities, temp_dir,
                  ['root', 'parquet'], 'parquet')

        mock_science_container.return_value.await_response.side_effect = ["failure",
                                                                          "success."]

        # Call the task
        transform_file(
            request_id=test_request_id,
            file_id=test_file_id,
            paths=test_paths,
            service_endpoint=test_service_endpoint,
            result_destination="volume",
            result_format="parquet"
        )

        science_request = mock_science_container.return_value.send.call_args[0][0]
        assert science_request["safeOutputFileName"] == '/local/results/site2:file.root.parquet'
        mock_servicex_adapter.return_value.put_file_complete.assert_called_once()
        assert mock_servicex_adapter.return_value. \
            put_file_complete.call_args[0][0].status == 'success'


def test_transformer_long_filename(args, mock_celery, transformer_capabilities,
                                   mock_servicex_adapter,
                                   mock_object_store_uploader, mock_input_queue,
                                   mock_object_store_manager,
                                   mock_science_container):
    with tempfile.TemporaryDirectory() as temp_dir:
        init_test(args, mock_celery, transformer_capabilities, temp_dir,
                  ['root', 'parquet'], 'parquet')

        object_store_uploader_args = mock_object_store_uploader.call_args.kwargs
        assert object_store_uploader_args["request_id"] == '1234'
        assert object_store_uploader_args["convert_root_to_parquet"] is False

        mock_science_container.return_value.await_response.side_effect = ["failure",
                                                                          "success."]

        long_filename = "rootfile12"*300
        # Call the task
        transform_file(
            request_id=test_request_id,
            file_id=test_file_id,
            paths=[long_filename],
            service_endpoint=test_service_endpoint,
            result_destination=test_result_destination,
            result_format="parquet"
        )

        science_request = mock_science_container.return_value.send.call_args[0][0]
        assert science_request["safeOutputFileName"] != long_filename
        assert len(science_request["safeOutputFileName"]) - \
               len(os.path.join(args.shared_dir, test_request_id, 'scratch')) == 256


def test_hash_path():
    from transformer_sidecar.transformer import hash_path

    # Short names not messed with
    assert hash_path("root://site1/file.root") == "root://site1/file.root"

    # Long names are hashed
    assert len(hash_path('rootfile12'*300)) == 255


def test_transform_file(args, mock_celery, transformer_capabilities,
                        mock_servicex_adapter,
                        mock_object_store_uploader, mock_input_queue,
                        mock_object_store_manager,
                        mock_science_container):
    with (tempfile.TemporaryDirectory() as temp_dir):
        init_test(args, mock_celery, transformer_capabilities, temp_dir,
                  ['root', 'parquet'], 'root')

        mock_science_container.return_value.await_response.side_effect = ["failure", "success."]

        # Call the task
        transform_file(
            request_id=test_request_id,
            file_id=test_file_id,
            paths=test_paths,
            service_endpoint=test_service_endpoint,
            result_destination=test_result_destination,
            result_format=test_result_format
        )
        mock_science_container.assert_called_once()

        assert os.path.isdir(os.path.join(temp_dir, "test-request-123"))
        assert os.path.isdir(os.path.join(temp_dir, "test-request-123", "scratch"))

        mock_servicex_adapter.called_with(test_service_endpoint)
        success_result = mock_input_queue.return_value.put.call_args[0][0]

        assert success_result.rec.file_path == test_paths[1]
        assert success_result.rec.file_id == test_file_id
        assert success_result.rec.status == "success"
        assert success_result.source_path == PosixPath(
            os.path.join(temp_dir, "test-request-123", "scratch", test_paths[1])
        )


def test_transform_file_hard_failure(args, mock_celery,
                                     transformer_capabilities,
                                     mock_servicex_adapter,
                                     mock_object_store_uploader, mock_input_queue,
                                     mock_object_store_manager,
                                     mock_science_container):
    with (tempfile.TemporaryDirectory() as temp_dir):
        init_test(args, mock_celery, transformer_capabilities, temp_dir,
                  ['root', 'parquet'], 'root')

        mock_science_container.return_value.await_response.side_effect = ["failure",
                                                                          "failure"]
        transform_file(
            request_id=test_request_id,
            file_id=test_file_id,
            paths=test_paths,
            service_endpoint=test_service_endpoint,
            result_destination=test_result_destination,
            result_format=test_result_format
        )
        mock_science_container.assert_called_once()

        assert os.path.isdir(os.path.join(temp_dir, "test-request-123"))
        assert os.path.isdir(os.path.join(temp_dir, "test-request-123", "scratch"))

        mock_servicex_adapter.called_with(test_service_endpoint)
        mock_input_queue.return_value.put.assert_not_called()
        mock_servicex_adapter.return_value.put_file_complete.assert_called_once()
        failure_report = mock_servicex_adapter.return_value.put_file_complete.call_args[0][0]
        assert failure_report.status == "failure"
        assert failure_report.file_path == test_paths[0]
        assert failure_report.file_id == test_file_id
        assert failure_report.request_id == test_request_id


def test_transform_file_exception(args, mock_celery,
                                  transformer_capabilities,
                                  mock_servicex_adapter,
                                  mock_object_store_uploader, mock_input_queue,
                                  mock_object_store_manager,
                                  mock_science_container):
    with (tempfile.TemporaryDirectory() as temp_dir):
        init_test(args, mock_celery, transformer_capabilities, temp_dir,
                  ['root', 'parquet'], 'root')

        mock_science_container.return_value.await_response.side_effect = Exception("Test Exception")  # noqa E501

        transform_file(
            request_id=test_request_id,
            file_id=test_file_id,
            paths=test_paths,
            service_endpoint=test_service_endpoint,
            result_destination=test_result_destination,
            result_format=test_result_format
        )

        mock_servicex_adapter.return_value.put_file_complete.assert_called_once()
        failure_report = mock_servicex_adapter.return_value.put_file_complete.call_args[0][0]
        assert failure_report.status == "failure"
        assert failure_report.file_path == test_paths[0]
        assert failure_report.file_id == test_file_id
        assert failure_report.request_id == test_request_id


@contextlib.contextmanager
def temporary_signal_handler(sig, handler):
    original_handler = signal.getsignal(sig)
    signal.signal(sig, handler)
    try:
        yield
    finally:
        signal.signal(sig, original_handler)


def test_prioritize_replicas():
    replicas = ["http://site1/file1.root", "root://site3/file3.root",
                "http://site2/file2.root", "root://site1/file1.root"]

    prioritized_replicas = prioritize_replicas(replicas)
    assert prioritized_replicas == ["root://site3/file3.root", "root://site1/file1.root",
                                    "http://site1/file1.root", "http://site2/file2.root"]


def test_prepend_xcache():
    # First test with no xcache
    os.environ["CACHE_PREFIX"] = ""

    replicas = ["root://site3/file3.root", "root://site1/file1.root"]
    assert prepend_xcache(replicas) == replicas

    # Now test with single xcache
    os.environ["CACHE_PREFIX"] = "//xcache-cms-local:"
    assert prepend_xcache(replicas) == ["root:////xcache-cms-local://root://site3/file3.root",
                                        "root:////xcache-cms-local://root://site1/file1.root"]

    # Now test with multiple xcache
    os.environ["CACHE_PREFIX"] = "//xcache-cms-local-1,//xcache-cms-local-2"
    big_replica_list = []
    for i in range(100):
        big_replica_list.append(f"root://site{i}/file{i}.root")

    prepended1 = prepend_xcache(big_replica_list)

    # Shuffle the list and check that the replicas are still assigned to the same xcache
    random.shuffle(big_replica_list)
    prepended2 = prepend_xcache(big_replica_list)
    assert sorted(prepended1) == sorted(prepended2)
