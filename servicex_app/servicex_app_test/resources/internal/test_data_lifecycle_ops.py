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
from datetime import datetime
from unittest.mock import patch, ANY

from pytest import fixture, mark

from servicex_app.models import Dataset, TransformationResult, TransformRequest, \
    DatasetFile
from servicex_app_test.resource_test_base import ResourceTestBase
from servicex_app.resources.internal.data_lifecycle_ops import DataLifecycleOps


class TestDataLifecycleOps(ResourceTestBase):
    module = "servicex_app.resources.internal.data_lifecycle_ops"

    @fixture(scope="function")
    def db_session(self):
        from sqlalchemy import create_engine
        from servicex_app.models import db
        engine = create_engine("sqlite:///:memory:")
        db.metadata.create_all(engine)
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()

        yield session

        session.close()
        db.metadata.drop_all(engine)

    @fixture
    def mock_db(self, mocker):
        db = mocker.patch(f"{self.module}.db")
        db.session = mocker.Mock()
        db.session.begin = mocker.MagicMock()
        return db

    @fixture
    def mock_session(self, mocker):
        return mocker.MagicMock()

    @fixture
    def mock_find_expired(self, mocker):
        mock_transform_request_cls = mocker.patch(f"{self.module}.TransformRequest")
        transform = self._generate_transform_request()
        mock_transform_request_cls.find_expired.return_value = [transform]
        return mock_transform_request_cls.find_expired

    @fixture
    def mock_find_orphaned(self, mocker, mock_db):
        # Create the mock
        mock_execute = mocker.Mock()

        results = [
            Dataset(last_used=datetime(2022, 1, 1),
                    last_updated=datetime(2022, 1, 1),
                    id='123',
                    name='dataset1',
                    events=100,
                    size=1000,
                    n_files=1,
                    lookup_status='looking',
                    did_finder='rucio')
        ]

        # Chain the mocks to match the call pattern
        mock_execute.return_value.scalars.return_value.all.return_value = results

        mock_db.session.execute = mock_execute
        return results

    @fixture
    def mock_transform_result(self, mocker):
        mock_transform_result_cls = mocker.patch(f"{self.module}.TransformationResult")
        mock_transform_result_cls.query = mocker.MagicMock()
        mock_transform_result_cls.query.filter_by = mocker.MagicMock()
        return mock_transform_result_cls

    @fixture
    def mock_dataset_files(self, mocker):
        mock_transform_result_cls = mocker.patch(f"{self.module}.DatasetFile")
        mock_transform_result_cls.query = mocker.MagicMock()
        mock_transform_result_cls.query.filter_by = mocker.MagicMock()
        return mock_transform_result_cls

    @fixture
    def mock_select(self, mocker):
        return mocker.patch(f"{self.module}.select")

    @fixture
    def mock_exists(self, mocker):
        return mocker.patch(f"{self.module}.exists")

    @fixture
    def insert_transforms(self, db_session):
        active_transform = self._generate_transform_request()
        active_transform.submit_time = datetime(2022, 1, 1, 0, 0)
        active_transform.request_id = 1
        active_transform.did_id = 1
        active_transform.title = 'active'
        db_session.add(active_transform)

        active_result = TransformationResult(
            request_id=1,
            file_path='file_path',
            transform_status='complete',
        )
        db_session.add(active_result)

        stale_transform = self._generate_transform_request()
        stale_transform.submit_time = datetime(2021, 1, 1, 0, 0)
        stale_transform.request_id = 2
        stale_transform.did_id = 1
        stale_transform.title = 'stale'
        db_session.add(stale_transform)
        stale_result = TransformationResult(
            request_id=2,
            file_path='file_path',
            transform_status='complete',
        )
        db_session.add(stale_result)

        db_session.commit()
        return {"active": active_transform, "stale": stale_transform}

    @fixture
    def insert_datasets(self, db_session, insert_transforms):
        dataset = Dataset(
            last_used=datetime(2022, 1, 1),
            last_updated=datetime(2022, 1, 1),
            id=1,
            name='not-orphaned',
            events=100,
            size=1000,
            n_files=1,
            lookup_status='looking',
            did_finder='rucio'
        )
        db_session.add(dataset)
        db_session.add(DatasetFile(
            dataset_id=1,
            paths='file_path'
        ))

        dataset = Dataset(
            last_used=datetime(2022, 1, 1),
            last_updated=datetime(2022, 1, 1),
            id=2,
            name='orphaned',
            events=100,
            size=1000,
            n_files=1,
            lookup_status='looking',
            did_finder='rucio'
        )
        db_session.add(dataset)
        db_session.add(DatasetFile(
            dataset_id=2,
            paths='file_path'
        ))

        db_session.commit()
        return dataset

    @mark.parametrize("use_object_store", [
        True,  # Enable Object store
        False  # No object store
    ])
    def test_expired_transforms(self, use_object_store, mocker, insert_transforms,
                                db_session):

        data_life_cycle_ops = DataLifecycleOps()

        mock_object_store = mocker.MagicMock() if use_object_store else None

        response = data_life_cycle_ops.delete_expired_transforms(db_session,
                                                                 mock_object_store,
                                                                 cutoff_timestamp=datetime
                                                                 .fromisoformat('2021-01-01T00:00:00'))

        assert len(response) == 1
        remaining_transforms = db_session.query(TransformRequest).all()
        assert len(remaining_transforms) == 1
        assert remaining_transforms[0].title == 'active'

        remaining_results = db_session.query(TransformationResult).all()
        assert len(remaining_results) == 1
        if use_object_store:
            mock_object_store.delete_bucket_and_contents.assert_called_with('2')

    def test_orphaned_datasets(self, insert_datasets, db_session):
        data_life_cycle_ops = DataLifecycleOps()
        response = data_life_cycle_ops.delete_orphaned_datasets(db_session)
        assert len(response) == 1

        remaining_datasets = db_session.query(Dataset).all()
        assert len(remaining_datasets) == 1
        assert remaining_datasets[0].name == 'not-orphaned'

        assert len(db_session.query(DatasetFile).all()) == 1

    @patch('servicex_app.resources.internal.data_lifecycle_ops.DataLifecycleOps.delete_expired_transforms',
           return_value=['expired'])
    @patch('servicex_app.resources.internal.data_lifecycle_ops.DataLifecycleOps.delete_orphaned_datasets',
           return_value=['orphaned'])
    def test_post(self, mock_orphaned, mock_delete_expired, mocker):
        client = self._test_client()
        with client.application.app_context():
            response = client.post('/servicex/internal/data-lifecycle',
                                   query_string={'cutoff_timestamp': '2021-01-01T00:00:00'})

        assert response.status_code == 200
        assert response.json == {
            "deleted_transforms": ['expired'],
            "deleted_datasets": ['orphaned']
        }
        mock_delete_expired.assert_called_with(session=ANY,
                                               object_store=None,
                                               cutoff_timestamp=datetime.fromisoformat('2021-01-01T00:00:00'))

        mock_orphaned.assert_called_with(ANY)

    @patch('servicex_app.resources.internal.data_lifecycle_ops.DataLifecycleOps.delete_expired_transforms',
           return_value=[])
    @patch('servicex_app.resources.internal.data_lifecycle_ops.DataLifecycleOps.delete_orphaned_datasets',
           return_value=[])
    def test_post_no_op(self, mock_orphaned, mock_delete_expired, mocker):
        client = self._test_client()
        with client.application.app_context():
            response = client.post('/servicex/internal/data-lifecycle',
                                   query_string={'cutoff_timestamp': '2021-01-01T00:00:00'})

        assert response.status_code == 200
        assert response.json == {
            "deleted_transforms": [],
            "deleted_datasets": []
        }
        mock_delete_expired.assert_called_with(session=ANY,
                                               object_store=None,
                                               cutoff_timestamp=datetime.fromisoformat('2021-01-01T00:00:00'))

        mock_orphaned.assert_called_with(ANY)
