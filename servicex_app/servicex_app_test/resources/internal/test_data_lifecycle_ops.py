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
from unittest.mock import ANY

from pytest import fixture, mark

from servicex_app.models import (
    Dataset,
    DatasetFile,
    TransformRequest,
    TransformationResult,
)
from servicex_app.resources.internal.data_lifecycle_ops import DataLifecycleOps
from servicex_app_test.resource_test_base import ResourceTestBase


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
            Dataset(
                last_used=datetime(2022, 1, 1),
                last_updated=datetime(2022, 1, 1),
                id="123",
                name="dataset1",
                events=100,
                size=1000,
                n_files=1,
                lookup_status="looking",
                did_finder="rucio",
            )
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
        active_transform.output_path = "1"
        active_transform.did_id = 1
        active_transform.title = "active"
        db_session.add(active_transform)

        active_result = TransformationResult(
            request_id=1,
            file_path="file_path",
            transform_status="complete",
        )
        db_session.add(active_result)

        stale_transform = self._generate_transform_request()
        stale_transform.submit_time = datetime(2021, 1, 1, 0, 0)
        stale_transform.request_id = 2
        stale_transform.output_path = "2"
        stale_transform.did_id = 1
        stale_transform.title = "stale"
        db_session.add(stale_transform)
        stale_result = TransformationResult(
            request_id=2,
            file_path="file_path",
            transform_status="complete",
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
            name="not-orphaned",
            events=100,
            size=1000,
            n_files=1,
            lookup_status="looking",
            did_finder="rucio",
        )
        db_session.add(dataset)
        db_session.add(DatasetFile(dataset_id=1, paths="file_path"))

        dataset = Dataset(
            last_used=datetime(2022, 1, 1),
            last_updated=datetime(2022, 1, 1),
            id=2,
            name="orphaned",
            events=100,
            size=1000,
            n_files=1,
            lookup_status="looking",
            did_finder="rucio",
        )
        db_session.add(dataset)
        db_session.add(DatasetFile(dataset_id=2, paths="file_path"))

        db_session.commit()
        return dataset

    @mark.parametrize(
        "use_object_store", [True, False]  # Enable Object store  # No object store
    )
    def test_expired_transforms(
        self, use_object_store, mocker, insert_transforms, db_session
    ):

        data_life_cycle_ops = DataLifecycleOps()

        mock_object_store = mocker.MagicMock() if use_object_store else None

        response = data_life_cycle_ops.delete_expired_transforms(
            db_session,
            mock_object_store,
            cutoff_timestamp=datetime.fromisoformat("2021-01-01T00:00:00"),
        )

        assert len(response) == 1
        remaining_transforms = db_session.query(TransformRequest).all()
        assert len(remaining_transforms) == 1
        assert remaining_transforms[0].title == "active"

        remaining_results = db_session.query(TransformationResult).all()
        assert len(remaining_results) == 1
        if use_object_store:
            mock_object_store.delete_bucket_and_contents.assert_called_with("2")

    def test_orphaned_datasets(self, insert_datasets, db_session):
        data_life_cycle_ops = DataLifecycleOps()
        response = data_life_cycle_ops.delete_orphaned_datasets(db_session)
        assert len(response) == 1

        remaining_datasets = db_session.query(Dataset).all()
        assert len(remaining_datasets) == 1
        assert remaining_datasets[0].name == "not-orphaned"

        assert len(db_session.query(DatasetFile).all()) == 1

    @fixture
    def mock_delete_expired(self, mocker):
        mock = mocker.patch(f"{self.module}.DataLifecycleOps.delete_expired_transforms")
        mock.return_value = ("expired",)
        yield mock

    @fixture
    def mock_orphaned(self, mocker):
        mock = mocker.patch(f"{self.module}.DataLifecycleOps.delete_orphaned_datasets")
        mock.return_value = ("orphaned",)
        yield mock

    @fixture
    def mock_transform_request(self, mocker):
        mock = mocker.patch(f"{self.module}.TransformRequest")
        yield mock

    @mark.parametrize(
        "max_cache_size, cache_size, reduce_by",
        [
            ("5000", 7000, 7000 - 5000),
            ("5Mb", 7 * 1024**2, 7 * 1024**2 - 5 * 1024**2),
            ("5Gb", 7 * 1024**3, 7 * 1024**3 - 5 * 1024**3),
            ("5Tb", 7 * 1024**4, 7 * 1024**4 - 5 * 1024**4),
            ("5Pb", 7 * 1024**5, 7 * 1024**5 - 5 * 1024**5),
        ],
    )
    def test_post(
        self,
        mock_transform_request,
        mock_orphaned,
        mock_delete_expired,
        max_cache_size,
        cache_size,
        reduce_by,
    ):
        client = self._test_client(
            extra_config={"MAX_DESIRED_TRANSFORM_CACHE_SIZE": max_cache_size}
        )
        mock_transform_request.total_cache_size.side_effect = [
            cache_size,
            cache_size - reduce_by,
        ]

        # In this test we don't want to delete transforms based on reducing the size of the
        # cache. We will delete transforms on by the cutoff timestamp.
        mock_transform_request.latest_request_to_accumulated_cache_size.return_value = (
            datetime.fromisoformat("2021-01-04T14:30:00")
        )

        with client.application.app_context():
            response = client.post(
                "/servicex/internal/data-lifecycle",
                query_string={"cutoff_timestamp": "2021-01-01T00:00:00"},
            )

        assert response.status_code == 200
        assert response.json == {
            "cutoff_timestamp": "2021-01-01T00:00:00",
            "deleted_transforms": ["expired"],
            "deleted_datasets": ["orphaned"],
            "total_bytes_after": cache_size - reduce_by,
            "total_bytes_before": cache_size,
        }
        mock_delete_expired.assert_called_with(
            session=ANY,
            object_store=None,
            cutoff_timestamp=datetime.fromisoformat("2021-01-01T00:00:00"),
        )

        mock_orphaned.assert_called_with(ANY)

    def test_post_reduce_cache(
        self, mock_transform_request, mock_orphaned, mock_delete_expired
    ):
        client = self._test_client(
            extra_config={"MAX_DESIRED_TRANSFORM_CACHE_SIZE": "5000"}
        )
        mock_transform_request.total_cache_size.side_effect = [7000, 5000]

        # In this test we want to delete transforms based on reducing the size of the
        # cache, going earlier in time from the cutoff timestamp.
        cache_reduce_timestamp = "2021-01-01T14:30:00"
        mock_transform_request.latest_request_to_accumulated_cache_size.return_value = (
            datetime.fromisoformat(cache_reduce_timestamp)
        )

        with client.application.app_context():
            response = client.post(
                "/servicex/internal/data-lifecycle",
                query_string={"cutoff_timestamp": "2021-02-01T00:00:00"},
            )

        assert response.status_code == 200
        mock_transform_request.latest_request_to_accumulated_cache_size.assert_called_with(
            2000
        )

        assert response.json == {
            "cutoff_timestamp": cache_reduce_timestamp,
            "deleted_transforms": ["expired"],
            "deleted_datasets": ["orphaned"],
            "total_bytes_after": 5000,
            "total_bytes_before": 7000,
        }
        mock_delete_expired.assert_called_with(
            session=ANY,
            object_store=None,
            cutoff_timestamp=datetime.fromisoformat(cache_reduce_timestamp),
        )

        mock_orphaned.assert_called_with(ANY)

    def test_small_cache(
        self, mock_transform_request, mock_orphaned, mock_delete_expired
    ):
        client = self._test_client(
            extra_config={"MAX_DESIRED_TRANSFORM_CACHE_SIZE": "5000"}
        )

        # In this test, the current size of the cache is smaller than the threshold.
        mock_transform_request.total_cache_size.side_effect = [4000, 4000]

        cutoff_timestamp = "2021-02-01T00:00:00"

        with client.application.app_context():
            response = client.post(
                "/servicex/internal/data-lifecycle",
                query_string={"cutoff_timestamp": cutoff_timestamp},
            )
        assert response.status_code == 200
        # We don't need to worry about final cache size since we are below the threshold
        # We will only delete based on the cutoff timestamp.
        mock_transform_request.latest_request_to_accumulated_cache_size.assert_not_called()
        assert response.json == {
            "cutoff_timestamp": cutoff_timestamp,
            "deleted_transforms": ["expired"],
            "deleted_datasets": ["orphaned"],
            "total_bytes_after": 4000,
            "total_bytes_before": 4000,
        }

        mock_delete_expired.assert_called_with(
            session=ANY,
            object_store=None,
            cutoff_timestamp=datetime.fromisoformat(cutoff_timestamp),
        )

        mock_orphaned.assert_called_with(ANY)

    def test_no_cache(self, mock_transform_request, mock_orphaned, mock_delete_expired):
        client = self._test_client(
            extra_config={"MAX_DESIRED_TRANSFORM_CACHE_SIZE": "5000"}
        )
        mock_transform_request.total_cache_size.side_effect = [0, 0]

        cutoff_timestamp = "2021-02-01T00:00:00"
        mock_transform_request.latest_request_to_accumulated_cache_size.return_value = (
            None
        )

        with client.application.app_context():
            response = client.post(
                "/servicex/internal/data-lifecycle",
                query_string={"cutoff_timestamp": cutoff_timestamp},
            )
        assert response.status_code == 200
        mock_transform_request.latest_request_to_accumulated_cache_size.assert_not_called()
        assert response.json == {
            "cutoff_timestamp": cutoff_timestamp,
            "deleted_transforms": ["expired"],
            "deleted_datasets": ["orphaned"],
            "total_bytes_after": 0,
            "total_bytes_before": 0,
        }

        mock_delete_expired.assert_called_with(
            session=ANY,
            object_store=None,
            cutoff_timestamp=datetime.fromisoformat(cutoff_timestamp),
        )

        mock_orphaned.assert_called_with(ANY)

    def test_no_config_value(
        self, mock_transform_request, mock_orphaned, mock_delete_expired
    ):
        client = self._test_client(
            extra_config={}
        )  # No MAX_DESIRED_TRANSFORM_CACHE_SIZE

        mock_transform_request.total_cache_size.side_effect = [0, 0]

        cutoff_timestamp = "2021-02-01T00:00:00"

        with client.application.app_context():
            response = client.post(
                "/servicex/internal/data-lifecycle",
                query_string={"cutoff_timestamp": cutoff_timestamp},
            )
        assert response.status_code == 200
        mock_transform_request.latest_request_to_accumulated_cache_size.assert_not_called()

    def test_post_no_op(
        self, mock_orphaned, mock_delete_expired, mock_transform_request
    ):
        """
        In this test, no transforms are expired and no datasets are orphaned.
        """
        client = self._test_client(
            extra_config={"MAX_DESIRED_TRANSFORM_CACHE_SIZE": "5000"}
        )
        mock_transform_request.total_cache_size.side_effect = [7000, 7000]

        mock_orphaned.return_value = []
        mock_delete_expired.return_value = []

        cache_reduce_timestamp = "2021-01-01T14:30:00"
        mock_transform_request.latest_request_to_accumulated_cache_size.return_value = (
            datetime.fromisoformat(cache_reduce_timestamp)
        )

        with client.application.app_context():
            response = client.post(
                "/servicex/internal/data-lifecycle",
                query_string={"cutoff_timestamp": "2021-01-01T00:00:00"},
            )

        assert response.status_code == 200
        assert response.json == {
            "cutoff_timestamp": "2021-01-01T00:00:00",
            "deleted_datasets": [],
            "deleted_transforms": [],
            "total_bytes_after": 7000,
            "total_bytes_before": 7000,
        }

        mock_delete_expired.assert_called_with(
            session=ANY,
            object_store=None,
            cutoff_timestamp=datetime.fromisoformat("2021-01-01T00:00:00"),
        )

        mock_orphaned.assert_called_with(ANY)
