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
from datetime import datetime, timezone
from unittest.mock import ANY

from pytest import fixture
from servicex_app import LookupResultProcessor
from servicex_app_test.resource_test_base import ResourceTestBase

from servicex_app.dataset_manager import DatasetManager

from servicex_app.models import (
    Dataset,
    DatasetFile,
    DatasetStatus,
    TransformRequest,
    TransformStatus,
    db,
)

CELERY = {"ORCHESTRATOR": "celery"}
TEMPORAL = {"ORCHESTRATOR": "temporal"}

FILE_URL = "/servicex/internal/transformation/{}/files"


def _record(name, size=1024, file_key=None):
    record = {
        "paths": [f"/foo/{name}", f"/bar/{name}"],
        "adler32": "12345",
        "file_size": size,
        "file_events": 500,
    }
    if file_key:
        record["file_key"] = file_key
    return record


class TestAddFileToDataset(ResourceTestBase):
    @fixture
    def mock_transformer_lookup(self, mocker):
        first_request = self._generate_transform_request()
        first_request.request_id = "first_request"
        first_request.staus = "Running"
        first_request.files = 0

        second_request = self._generate_transform_request()
        second_request.request_id = "second_request"
        second_request.status = "Submitted"
        second_request.files = 0

        mock_transformer_lookup = mocker.patch.object(
            TransformRequest,
            "lookup_running_by_dataset_id",
            return_value=[first_request, second_request],
        )
        return mock_transformer_lookup

    @fixture
    def mock_dataset_manager_from_id(self, mocker):
        mock_dataset_manager = mocker.MagicMock(DatasetManager)
        mock_dataset_manager.name = "mock_dataset"
        mock_dataset_manager.id = 42
        mock_dataset_manager.dataset = mocker.Mock()
        mock_dataset_manager.dataset.id = 42
        mock_dataset_manager.add_files.return_value = []
        mock_dataset_manager.upsert_files.return_value = []

        mock_dataset_manager_find = mocker.patch.object(
            DatasetManager, "from_dataset_id", return_value=mock_dataset_manager
        )
        return mock_dataset_manager_find

    # --- mocked DatasetManager ---------------------------------------------------

    def test_put_new_file_celery(
        self, mocker, mock_dataset_manager_from_id, mock_transformer_lookup
    ):
        mock_add_files = mock_dataset_manager_from_id.return_value.add_files
        mock_processor = mocker.MagicMock(LookupResultProcessor)

        client = self._test_client(
            extra_config=CELERY, lookup_result_processor=mock_processor
        )
        with client.application.app_context():
            response = client.put(FILE_URL.format(1234), json=_record("bar1.root"))
            assert response.status_code == 200
            assert response.json == {"dataset_id": "1234", "max_file_id": 0}

            mock_dataset_manager_from_id.assert_called_with("1234", ANY, ANY)
            mock_add_files.assert_called_once()
            records, running_requests, processor = mock_add_files.call_args[0]
            assert records == [_record("bar1.root")]
            assert len(running_requests) == 2
            assert processor is mock_processor
            mock_dataset_manager_from_id.return_value.upsert_files.assert_not_called()

    def test_put_new_file_bulk_celery(
        self, mocker, mock_transformer_lookup, mock_dataset_manager_from_id
    ):
        mock_add_files = mock_dataset_manager_from_id.return_value.add_files
        client = self._test_client(
            extra_config=CELERY,
            lookup_result_processor=mocker.MagicMock(LookupResultProcessor),
        )

        response = client.put(
            FILE_URL.format(1234),
            json=[_record("bar1.root"), _record("bar2.root", size=2048)],
        )
        assert response.status_code == 200
        assert response.json == {"dataset_id": "1234", "max_file_id": 0}
        records, running_requests, _ = mock_add_files.call_args[0]
        assert [r["paths"][0] for r in records] == ["/foo/bar1.root", "/foo/bar2.root"]
        assert [r.request_id for r in running_requests] == [
            "first_request",
            "second_request",
        ]

    def test_put_new_file_temporal(
        self, mocker, mock_dataset_manager_from_id, mock_transformer_lookup
    ):
        dataset_manager = mock_dataset_manager_from_id.return_value
        mock_processor = mocker.MagicMock(LookupResultProcessor)

        client = self._test_client(
            extra_config=TEMPORAL, lookup_result_processor=mock_processor
        )
        response = client.put(
            FILE_URL.format(1234), json=[_record("bar1.root"), _record("bar2.root")]
        )
        assert response.status_code == 200
        assert response.json == {"dataset_id": "1234", "max_file_id": 0}

        dataset_manager.upsert_files.assert_called_once_with(
            [_record("bar1.root"), _record("bar2.root")]
        )
        dataset_manager.add_files.assert_not_called()
        mock_transformer_lookup.assert_not_called()
        mock_processor.add_files_to_processing_queue.assert_not_called()

    def test_put_new_file_reports_max_file_id(
        self, mocker, mock_transformer_lookup, mock_dataset_manager_from_id
    ):
        dataset_manager = mock_dataset_manager_from_id.return_value
        dataset_manager.upsert_files.return_value = [
            DatasetFile(id=19),
            DatasetFile(id=17),
        ]

        client = self._test_client(extra_config=TEMPORAL)
        response = client.put(
            FILE_URL.format(1234),
            json=[_record("bar1.root", file_key="scope:bar1.root")],
        )
        assert response.status_code == 200
        assert response.json == {"dataset_id": "1234", "max_file_id": 19}

    def test_put_new_file_with_exception(self, client):
        with client.application.app_context():
            dataset = self._make_dataset()

        response = client.put(
            FILE_URL.format(dataset),
            json={
                "paths": [123, 123],
                "adler32": "12345",
                "file_size": 1024,
                "file_events": 500,
            },
        )
        assert response.status_code == 500
        assert response.json == {
            "message": "Something went wrong: sequence item 0: expected str instance, int found"
        }

    # --- real database ------------------------------------------------------------

    @staticmethod
    def _make_dataset() -> int:
        dataset = Dataset(
            name="rucio://scope:my-did",
            did_finder="rucio",
            lookup_status=DatasetStatus.looking,
            last_used=datetime.now(tz=timezone.utc),
            last_updated=datetime.now(tz=timezone.utc),
        )
        db.session.add(dataset)
        db.session.commit()
        return dataset.id

    def _make_lookup_request(self, dataset_id: int, request_id: str) -> None:
        request = self._generate_transform_request()
        request.request_id = request_id
        request.did_id = dataset_id
        request.status = TransformStatus.lookup
        request.files = 0
        db.session.add(request)
        db.session.commit()

    def test_put_celery_dispatches_to_running_requests(self, mocker):
        mock_processor = mocker.MagicMock(LookupResultProcessor)
        client = self._test_client(
            extra_config=CELERY, lookup_result_processor=mock_processor
        )
        with client.application.app_context():
            dataset_id = self._make_dataset()
            self._make_lookup_request(dataset_id, "req-1")

            response = client.put(
                FILE_URL.format(dataset_id),
                json=[
                    _record("a.root", file_key="scope:a.root"),
                    _record("b.root", file_key="scope:b.root"),
                ],
            )
            assert response.status_code == 200
            files = DatasetFile.query.filter_by(dataset_id=dataset_id).all()
            assert response.json == {
                "dataset_id": str(dataset_id),
                "max_file_id": max(f.id for f in files),
            }

            assert TransformRequest.lookup("req-1").files == 2
            mock_processor.add_files_to_processing_queue.assert_called_once()
            (request,) = mock_processor.add_files_to_processing_queue.call_args[0]
            sent = mock_processor.add_files_to_processing_queue.call_args[1]["files"]
            assert request.request_id == "req-1"
            assert sorted(f.file_key for f in sent) == ["scope:a.root", "scope:b.root"]

    def test_put_temporal_only_records_files(self, mocker):
        mock_server_tasks = mocker.patch(
            "servicex_app.lookup_result_processor.server_tasks"
        )
        lookup_running = mocker.spy(TransformRequest, "lookup_running_by_dataset_id")
        client = self._test_client(
            extra_config=TEMPORAL, lookup_result_processor=LookupResultProcessor()
        )
        with client.application.app_context():
            dataset_id = self._make_dataset()
            self._make_lookup_request(dataset_id, "req-1")

            batch = [
                _record("a.root", file_key="scope:a.root"),
                _record("b.root", file_key="scope:b.root"),
            ]
            response = client.put(FILE_URL.format(dataset_id), json=batch)
            assert response.status_code == 200
            files = DatasetFile.query.filter_by(dataset_id=dataset_id).all()
            max_id = max(f.id for f in files)
            assert response.json == {
                "dataset_id": str(dataset_id),
                "max_file_id": max_id,
            }

            # A retry that re-sends only files already stored updates them in place
            # and still reports the high-water mark.
            response = client.put(
                FILE_URL.format(dataset_id),
                json=[_record("b.root", size=4096, file_key="scope:b.root")],
            )
            assert response.status_code == 200
            assert response.json["max_file_id"] == max_id
            db.session.expire_all()
            files = DatasetFile.query.filter_by(dataset_id=dataset_id).all()
            assert len(files) == 2
            assert {f.file_key: f.file_size for f in files}["scope:b.root"] == 4096

            assert TransformRequest.lookup("req-1").files == 0
            lookup_running.assert_not_called()
            mock_server_tasks.add_files_to_processing_queue.delay.assert_not_called()
