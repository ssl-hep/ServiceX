# Copyright (c) 2019, IRIS-HEP
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
from datetime import timezone, datetime

from pytest import fixture

from servicex_app import LookupResultProcessor, TransformerManager
from servicex_app_test.resource_test_base import ResourceTestBase

from servicex_app.models import (
    DatasetFile,
    DatasetStatus,
    Dataset,
    TransformRequest,
    TransformStatus,
    db,
)


class TestFilesetComplete(ResourceTestBase):
    """
    These tests use real rows in a file-backed SQLite database, so the handler reads
    the counters as it does in production and a second app can report a
    file-complete callback in the middle of the fileset-complete request.
    """

    @fixture
    def db_config(self, tmp_path):
        return {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'servicex.db'}"}

    @fixture
    def transformer_manager(self, mocker):
        manager = mocker.MagicMock(TransformerManager)
        manager.shutdown_transformer_job = mocker.Mock()
        return manager

    @fixture
    def lookup_result_processor(self, mocker):
        return mocker.MagicMock(LookupResultProcessor)

    @fixture
    def client(self, db_config, transformer_manager, lookup_result_processor):
        return self._test_client(
            extra_config=db_config,
            transformation_manager=transformer_manager,
            lookup_result_processor=lookup_result_processor,
        )

    @staticmethod
    def _add_dataset(client, n_files=0) -> int:
        with client.application.app_context():
            dataset = Dataset(
                name="rucio://my-did",
                did_finder="rucio",
                lookup_status=DatasetStatus.looking,
                last_used=datetime.now(tz=timezone.utc),
                last_updated=datetime.now(tz=timezone.utc),
            )
            dataset.files = [
                DatasetFile(paths=f"/file{i}.root", adler32="xxx")
                for i in range(n_files)
            ]
            db.session.add(dataset)
            db.session.commit()
            return dataset.id

    @staticmethod
    def _add_request(
        client, dataset_id, request_id, status, files=0, files_completed=0
    ) -> None:
        with client.application.app_context():
            db.session.add(
                TransformRequest(
                    request_id=request_id,
                    did="rucio://my-did",
                    did_id=dataset_id,
                    submit_time=datetime.now(tz=timezone.utc),
                    result_destination="object-store",
                    result_format="parquet",
                    status=status,
                    app_version="1.0",
                    code_gen_image="sslhep/codegen:develop",
                    image="sslhep/transformer:develop",
                    files=files,
                    files_completed=files_completed,
                    files_failed=0,
                )
            )
            db.session.commit()

    @staticmethod
    def _request(client, request_id) -> TransformRequest:
        with client.application.app_context():
            transform_request = TransformRequest.lookup(request_id)
            db.session.expunge(transform_request)
            return transform_request

    @staticmethod
    def _fileset_complete(client, dataset_id, files):
        return client.put(
            f"/servicex/internal/transformation/{dataset_id}/complete",
            json={
                "files": files,
                "total-events": 1024,
                "total-bytes": 2046,
                "elapsed-time": 42,
            },
        )

    @staticmethod
    def _file_complete(client, request_id, file_id):
        return client.put(
            f"/servicex/internal/transformation/{request_id}/file-complete",
            json={
                "file-path": f"/file{file_id}.root",
                "file-id": file_id,
                "status": "success",
                "total-time": 1,
                "total-events": 10,
                "total-bytes": 10,
                "avg-rate": 1.0,
                "s3-object-name": f"file{file_id}",
            },
        )

    def test_put_fileset_complete(
        self, client, transformer_manager, lookup_result_processor
    ):
        dataset_id = self._add_dataset(client, n_files=3)
        self._add_request(client, dataset_id, "pending", TransformStatus.pending_lookup)
        self._add_request(
            client, dataset_id, "lookup", TransformStatus.lookup, 3, files_completed=1
        )

        response = self._fileset_complete(client, dataset_id, 3)
        assert response.status_code == 200

        with client.application.app_context():
            dataset = db.session.get(Dataset, dataset_id)
            assert dataset.lookup_status == DatasetStatus.complete
            assert dataset.n_files == 3
            assert dataset.events == 1024
            assert dataset.size == 2046

        # The pending request is sent the dataset and waits for its files
        pending_request = self._request(client, "pending")
        assert pending_request.status == TransformStatus.running
        assert pending_request.files == 3
        assert pending_request.finish_time is None
        lookup_result_processor.add_files_to_processing_queue.assert_called_once()

        lookup_request = self._request(client, "lookup")
        assert lookup_request.status == TransformStatus.running
        assert lookup_request.finish_time is None
        transformer_manager.shutdown_transformer_job.assert_not_called()

    def test_put_fileset_complete_all_files_already_done(
        self, client, transformer_manager
    ):
        dataset_id = self._add_dataset(client)
        self._add_request(client, dataset_id, "111-111", TransformStatus.lookup, 17, 17)

        response = self._fileset_complete(client, dataset_id, 17)
        assert response.status_code == 200

        transform_request = self._request(client, "111-111")
        assert transform_request.status == TransformStatus.complete
        assert transform_request.finish_time is not None
        transformer_manager.shutdown_transformer_job.assert_called_once_with(
            "111-111", "my-ws"
        )

    def test_put_fileset_complete_leaves_canceled_request(
        self, client, transformer_manager
    ):
        dataset_id = self._add_dataset(client)
        self._add_request(
            client, dataset_id, "111-111", TransformStatus.canceled, 17, 17
        )

        response = self._fileset_complete(client, dataset_id, 17)
        assert response.status_code == 200

        assert self._request(client, "111-111").status == TransformStatus.canceled
        transformer_manager.shutdown_transformer_job.assert_not_called()

    def test_put_fileset_complete_empty_dataset(self, client, transformer_manager):
        dataset_id = self._add_dataset(client)
        self._add_request(client, dataset_id, "111-111", TransformStatus.lookup)
        self._add_request(client, dataset_id, "222-222", TransformStatus.pending_lookup)

        response = self._fileset_complete(client, dataset_id, 0)
        assert response.status_code == 200

        for request_id in ("111-111", "222-222"):
            transform_request = self._request(client, request_id)
            assert transform_request.status == TransformStatus.complete
            assert transform_request.finish_time is not None
            transformer_manager.shutdown_transformer_job.assert_any_call(
                request_id, "my-ws"
            )
        assert transformer_manager.shutdown_transformer_job.call_count == 2

    def test_put_fileset_complete_shutdown_failure_keeps_status(
        self, client, transformer_manager
    ):
        dataset_id = self._add_dataset(client)
        self._add_request(client, dataset_id, "111-111", TransformStatus.lookup)
        self._add_request(client, dataset_id, "222-222", TransformStatus.lookup)
        transformer_manager.shutdown_transformer_job.side_effect = ConnectionError(
            "kubernetes api unreachable"
        )

        response = self._fileset_complete(client, dataset_id, 0)
        assert response.status_code == 200

        # The status was committed before the shutdown, and one failed shutdown
        # does not keep the other request's transformers running
        assert self._request(client, "111-111").status == TransformStatus.complete
        assert self._request(client, "222-222").status == TransformStatus.complete
        assert transformer_manager.shutdown_transformer_job.call_count == 2

    def test_put_fileset_complete_last_file_lands_during_lookup_close(
        self, mocker, client, db_config, transformer_manager
    ):
        """
        The last file-complete callback commits after fileset-complete has read the
        request but before it has written the status. The request must still end
        up complete with its transformers shut down, rather than stuck in running
        with no files remaining.
        """
        dataset_id = self._add_dataset(client)
        self._add_request(client, dataset_id, "req-1", TransformStatus.lookup, 3, 2)

        # The resources keep the transformer manager on the class, so both apps
        # share one
        callback_client = self._test_client(
            extra_config=db_config, transformation_manager=transformer_manager
        )

        lock_awaiting_dataset = TransformRequest.lock_awaiting_dataset
        callback_responses = []

        def interleaved(dataset_id):
            requests = lock_awaiting_dataset(dataset_id)
            callback_responses.append(self._file_complete(callback_client, "req-1", 3))
            return requests

        mocker.patch.object(
            TransformRequest, "lock_awaiting_dataset", side_effect=interleaved
        )

        response = self._fileset_complete(client, dataset_id, 3)
        assert response.status_code == 200
        assert [r.status_code for r in callback_responses] == [200]

        transform_request = self._request(client, "req-1")
        assert transform_request.status == TransformStatus.complete
        assert transform_request.files_remaining == 0
        assert transform_request.finish_time is not None
        # The request is completed and shut down exactly once
        transformer_manager.shutdown_transformer_job.assert_called_once_with(
            "req-1", "my-ws"
        )

    def test_put_fileset_complete_then_last_file(self, client, transformer_manager):
        dataset_id = self._add_dataset(client)
        self._add_request(client, dataset_id, "req-1", TransformStatus.lookup, 3, 2)

        response = self._fileset_complete(client, dataset_id, 3)
        assert response.status_code == 200
        assert self._request(client, "req-1").status == TransformStatus.running
        transformer_manager.shutdown_transformer_job.assert_not_called()

        response = self._file_complete(client, "req-1", 3)
        assert response.status_code == 200
        transform_request = self._request(client, "req-1")
        assert transform_request.status == TransformStatus.complete
        assert transform_request.finish_time is not None
        transformer_manager.shutdown_transformer_job.assert_called_once_with(
            "req-1", "my-ws"
        )
