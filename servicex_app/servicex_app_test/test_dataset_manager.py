# Copyright (c) 2022, IRIS-HEP
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

import pytest
from pytest import fixture
from servicex_app.dataset_manager import DatasetManager
from servicex_app.did_parser import DIDParser
from servicex_app.lookup_result_processor import LookupResultProcessor
from servicex_app.models import Dataset, DatasetFile, TransformRequest, DatasetStatus
from servicex_app.models import db
from servicex_app_test.resource_test_base import ResourceTestBase


def mock_dataset(status: str, mocker) -> Dataset:
    ds = mocker.MagicMock()
    ds.lookup_status = status
    ds.id = "da-tas-et-id"
    return ds


class TestDatasetManager(ResourceTestBase):

    @fixture
    def client(self):
        return self._test_client()

    @fixture
    def mock_dataset_cls(self, mocker):

        mock_dataset.save_to_db = mocker.Mock()
        mock_dataset_cls = mocker.patch("servicex_app.dataset_manager.Dataset", return_value=mock_dataset("created", mocker))
        mock_query = mocker.Mock(return_value=None)
        mock_dataset_cls.query.find_by_name = mock_query
        mock_dataset_cls.find_by_name.return_value = None
        return mock_dataset_cls

    @fixture
    def mock_dataset_file_cls(self, mocker):
        mock_dataset_file = DatasetFile(
            dataset_id="da-tas-et-id",
            paths="paths",
            adler32="adler32",
            file_size="file_size",
            file_events="file_events"
        )
        mock_dataset_file.save_to_db = mocker.Mock()
        mock_dataset_cls = mocker.patch("servicex_app.dataset_manager.DatasetFile", return_value=mock_dataset_file)
        return mock_dataset_cls

    def test_constructor(self, client):
        with client.application.app_context():
            d = Dataset()
            d.name = "rucio://my-did?files=1"
            dm = DatasetManager(dataset=d, logger=client.application.logger, db=db)
            assert dm.dataset == d

    def test_from_new_did(self, client):
        did = "rucio://my-did?files=1"
        with client.application.app_context():
            dm = DatasetManager.from_did(DIDParser(did), logger=client.application.logger,  db=db)
            assert dm.dataset.name == did
            assert dm.dataset.did_finder == "rucio"
            assert dm.dataset.lookup_status == DatasetStatus.created

            # See that the dataset is saved to the database
            assert dm.dataset.id is not None
            d_copy = Dataset.find_by_id(dm.dataset.id)
            assert d_copy
            assert d_copy.name == did

    def test_from_existing_did(self, client):
        did = "rucio://my-did?files=1"
        with client.application.app_context():
            d = Dataset(name=did, did_finder="rucio", lookup_status=DatasetStatus.looking,
                        last_used=datetime.now(tz=timezone.utc),
                        last_updated=datetime.fromtimestamp(0))
            d.save_to_db()
            dm = DatasetManager.from_did(DIDParser(did), logger=client.application.logger, db=db)
            assert dm.dataset.name == did
            assert dm.dataset.did_finder == "rucio"
            assert dm.dataset.lookup_status == DatasetStatus.looking
            assert dm.dataset.id == d.id

    def test_from_new_file_list(self, client):
        file_list = ["root://eospublic.cern.ch/1.root", "root://eospublic.cern.ch/2.root"]
        with client.application.app_context():
            dm = DatasetManager.from_file_list(file_list,
                                               logger=client.application.logger, db=db)
            assert dm.dataset.name == "985d119e9da637c5b7f89c133f60689259f0fe5db0ee4b3d993270aafdc5b82a"
            assert dm.dataset.did_finder == "user"
            assert dm.dataset.lookup_status == DatasetStatus.complete

            # See that the dataset is saved to the database
            assert dm.dataset.id is not None
            d_copy = Dataset.find_by_id(dm.dataset.id)
            assert d_copy
            assert d_copy.name == "985d119e9da637c5b7f89c133f60689259f0fe5db0ee4b3d993270aafdc5b82a"

    def test_from_existing_file_list(self, client):
        file_list = ["root://eospublic.cern.ch/1.root", "root://eospublic.cern.ch/2.root"]
        with client.application.app_context():
            d = Dataset(name=DatasetManager.file_list_hash(file_list),
                        did_finder="user", lookup_status=DatasetStatus.created,
                        last_used=datetime.now(tz=timezone.utc),
                        last_updated=datetime.fromtimestamp(0),
                        files=[
                            DatasetFile(
                                paths=file,
                                adler32="xxx",
                                file_events=0,
                                file_size=0
                            ) for file in file_list
                        ])
            d.save_to_db()
            dm = DatasetManager.from_file_list(file_list,
                                               logger=client.application.logger, db=db)
            assert dm.dataset.name == DatasetManager.file_list_hash(file_list)
            assert dm.dataset.did_finder == "user"
            assert dm.dataset.lookup_status == DatasetStatus.created
            assert dm.dataset.id == d.id

    def test_from_dataset_id(self, client):
        file_list = ["root://eospublic.cern.ch/1.root", "root://eospublic.cern.ch/2.root"]
        with client.application.app_context():
            d = Dataset(name=DatasetManager.file_list_hash(file_list),
                        did_finder="user", lookup_status=DatasetStatus.created,
                        last_used=datetime.now(tz=timezone.utc),
                        last_updated=datetime.fromtimestamp(0),
                        files=[
                            DatasetFile(
                                paths=file,
                                adler32="xxx",
                                file_events=0,
                                file_size=0
                            ) for file in file_list
                        ])
            d.save_to_db()
            dm = DatasetManager.from_dataset_id(d.id, logger=client.application.logger, db=db)
            assert dm.dataset.name == DatasetManager.file_list_hash(file_list)

    def test_from_dataset_id_not_found(self, client):
        with client.application.app_context():
            with pytest.raises(RuntimeError) as excinfo:
                _ = DatasetManager.from_dataset_id(42, logger=client.application.logger, db=db)
            assert str(excinfo.value) == "Could not find dataset with id 42"

    def test_lookup_required(self, client):
        with client.application.app_context():
            d = Dataset()
            d.name = "rucio://my-did?files=1"
            d.lookup_status = DatasetStatus.created
            dm = DatasetManager(dataset=d, logger=client.application.logger, db=db)

            assert dm.is_lookup_required

            dm.dataset.lookup_status = DatasetStatus.complete
            assert not dm.is_lookup_required

            dm.dataset.lookup_status = DatasetStatus.looking
            assert not dm.is_lookup_required

    def test_properties(self, client):
        with client.application.app_context():
            d = Dataset()
            d.name = "rucio://my-did?files=1"
            d.id = 42
            d.lookup_status = DatasetStatus.created
            dm = DatasetManager(dataset=d, logger=client.application.logger, db=db)

            assert dm.name == "rucio://my-did?files=1"
            assert dm.id == 42

    def test_file_list(self, client):
        with client.application.app_context():
            file_list = ["root://eospublic.cern.ch/1.root", "root://eospublic.cern.ch/2.root"]

            d = DatasetManager.from_file_list(file_list, logger=client.application.logger, db=db)
            assert d.file_paths == file_list

    def test_dataset_name_file_list(self, client):
        with client.application.app_context():
            file_list = ["root://eospublic.cern.ch/1.root", "root://eospublic.cern.ch/2.root"]

            dm = DatasetManager.from_file_list(file_list,
                                               logger=client.application.logger, db=db)
            assert dm.name == "985d119e9da637c5b7f89c133f60689259f0fe5db0ee4b3d993270aafdc5b82a"

    def test_dataset_name_did(self, client):
        with client.application.app_context():
            dm = DatasetManager.from_did(DIDParser("rucio://my-did?files=1"),
                                         logger=client.application.logger, db=db)
            assert dm.name == "rucio://my-did?files=1"

    def test_refresh(self, client):
        with client.application.app_context():
            dm = DatasetManager.from_did(DIDParser("rucio://my-did?files=1"),
                                         logger=client.application.logger, db=db)

            # To be fair, this test isn't really  verifying the refresh method, since
            # SQLAlchemy is serving the dataset instance out of a shared cache
            d2 = Dataset.find_by_id(dm.dataset.id)
            d2.lookup_status = DatasetStatus.complete
            d2.save_to_db()
            dm.refresh()
            assert dm.dataset.lookup_status == DatasetStatus.complete

    def test_is_complete(self, client):
        with client.application.app_context():
            d = Dataset()
            d.name = "rucio://my-did?files=1"
            d.id = 42
            d.lookup_status = DatasetStatus.created
            dm = DatasetManager(dataset=d, logger=client.application.logger, db=db)

            assert not dm.is_complete
            d.lookup_status = DatasetStatus.looking
            assert not dm.is_complete
            d.lookup_status = DatasetStatus.complete
            assert dm.is_complete

    def test_submit_lookup_request(self, mocker, client):
        mock_celery = mocker.Mock()
        with client.application.app_context():
            d = DatasetManager.from_did(did=DIDParser("rucio://my-did?files=1"),
                                        logger=client.application.logger, db=db)
            d.submit_lookup_request("http://hit-me/here", mock_celery)

            assert d.dataset.lookup_status == DatasetStatus.looking

        mock_celery.send_task.assert_called_with('did_finder_rucio.lookup_dataset', args=['my-did?files=1', 1, 'http://hit-me/here'])

    def test_publish_files(self, mocker, client):
        with client.application.app_context():
            mock_processor = mocker.MagicMock(spec=LookupResultProcessor)
            file_list = ["root://eospublic.cern.ch/1.root", "root://eospublic.cern.ch/2.root"]
            transform_request = TransformRequest()
            transform_request.request_id = "462-33"
            transform_request.selection = "test-string"

            d = DatasetManager.from_file_list(file_list, logger=client.application.logger, db=db)
            d.publish_files(request=transform_request, lookup_result_processor=mock_processor)
            assert transform_request.files == 2
            mock_processor.add_files_to_processing_queue.assert_called_with(transform_request, files=d.dataset.files)

    def test_add_files(self, mocker, client):
        with client.application.app_context():
            mock_processor = mocker.MagicMock(spec=LookupResultProcessor)
            file_list = ["root://eospublic.cern.ch/1.root", "root://eospublic.cern.ch/2.root"]
            first_request = self._generate_transform_request()
            first_request.request_id = "first_request"
            first_request.files = 2

            second_request = self._generate_transform_request()
            second_request.request_id = "second_request"
            second_request.files = 2

            d = DatasetManager.from_file_list(file_list, logger=client.application.logger,
                                              extras={"request_id": first_request.request_id},
                                              db=db)
            first_request.did_id = d.id
            second_request.did_id = d.id

            d.add_files(files=[
                DatasetFile(
                    paths="root://eospublic.cern.ch/3.root",
                    adler32="xxx",
                    file_events=0,
                    file_size=0
                )
            ], requests=[first_request, second_request], lookup_result_processor=mock_processor)

            assert first_request.files == 3
            assert second_request.files == 3
