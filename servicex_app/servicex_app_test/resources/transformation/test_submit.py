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
from unittest.mock import call

from pytest import fixture
from servicex_app.models import TransformRequest, DatasetStatus, TransformStatus

from servicex_app import LookupResultProcessor
from servicex_app.models import Dataset
from servicex_app.dataset_manager import DatasetManager

from servicex_app.code_gen_adapter import CodeGenAdapter

from servicex_app.transformer_manager import TransformerManager
from servicex_app_test.resource_test_base import ResourceTestBase


class TestSubmitTransformationRequest(ResourceTestBase):

    @staticmethod
    def _generate_transformation_request(**kwargs):
        request = {
            'did': '123-45-678',
            'selection': "test-string",
            'result-destination': 'object-store',
            'result-format': 'root-file',
            'workers': 10,
            'codegen': 'atlasxaod'
        }
        request.update(kwargs)
        return request

    @fixture
    def mock_dataset_manager_from_did(self, mocker):
        dm = mocker.Mock()
        dm.dataset = Dataset(name="rucio://123-45-678",
                             did_finder="rucio", lookup_status=DatasetStatus.looking,
                             last_used=datetime.now(tz=timezone.utc),
                             last_updated=datetime.fromtimestamp(0))

        dm.name = "rucio://123-45-678"
        dm.id = 42

        mock_from_did = mocker.patch.object(DatasetManager, "from_did", return_value=dm)
        return mock_from_did

    @fixture
    def file_list(self):
        return ["root://eospublic.cern.ch/1.root", "root://eospublic.cern.ch/2.root"]

    @fixture
    def mock_dataset_manager_from_files(self, mocker, file_list):
        hash = DatasetManager.file_list_hash(file_list)
        dm = mocker.Mock()
        dm.dataset = Dataset(name=hash,
                             did_finder="user", lookup_status=DatasetStatus.complete,
                             last_used=datetime.now(tz=timezone.utc),
                             last_updated=datetime.fromtimestamp(0))

        dm.name = hash
        dm.id = 43

        mock_from_file_list = mocker.patch.object(
            DatasetManager, "from_file_list", return_value=dm)
        return mock_from_file_list

    @fixture
    def mock_codegen(self, mocker):
        mock_code_gen = mocker.MagicMock(CodeGenAdapter)
        mock_code_gen.generate_code_for_selection.return_value = ('my-cm',
                                                                  'ssl-hep/func_adl:latest',
                                                                  'bash', 'echo')
        return mock_code_gen

    @fixture
    def mock_transform_manager(self, mocker):
        mock = mocker.MagicMock(TransformerManager)
        mock.start_transformers = mocker.Mock()
        return mock

    def test_submit_transformation_request_bad(self):
        client = self._test_client()

        resp = client.post('/servicex/transformation', json={'timestamp': '20190101'})
        assert resp.status_code == 400

    def test_submit_transformation_bad_result_dest(self):
        client = self._test_client()

        request = self._generate_transformation_request()
        request['result-destination'] = 'foo'
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400

    def test_submit_transformation_bad_wrong_dest_for_format(self):
        client = self._test_client()
        request = self._generate_transformation_request()
        request['result-format'] = 'root-file'
        request['result-destination'] = 'minio'
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400

    def test_submit_transformation_bad_result_format(self):
        client = self._test_client()
        request = self._generate_transformation_request()
        request['result-format'] = 'foo'
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400

    def test_submit_transformation_bad_did_scheme(self):
        client = self._test_client()
        request = self._generate_transformation_request(did='foobar://my-did')
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400
        assert "DID scheme is not supported" in response.json["message"]

    def test_submit_transformation_bad_code_gen_image(self, client):
        request = self._generate_transformation_request(codegen='foo')
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 500
        assert "Invalid Codegen Image Passed in Request: foo" in response.json[
            "message"]

    def test_submit_transformation_request_throws_exception(
            self, mocker, mock_rabbit_adaptor, mock_dataset_manager_from_did,
            mock_codegen, mock_app_version, mock_transform_manager):
        mock_rabbit_adaptor.setup_queue = mocker.Mock(side_effect=Exception('Test'))
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor,
                                   transformation_manager=mock_transform_manager,
                                   code_gen_service=mock_codegen)
        with client.application.app_context():
            response = client.post('/servicex/transformation',
                                   json=self._generate_transformation_request(),
                                   headers=self.fake_header()
                                   )
            assert response.status_code == 503
            assert response.json == {"message": "Error setting up transformer queues"}

    def test_submit_transformation(self, mock_rabbit_adaptor,
                                   mock_dataset_manager_from_did,
                                   mock_codegen,
                                   mock_app_version):
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor,
                                   code_gen_service=mock_codegen)
        with client.application.app_context():
            request = self._generate_transformation_request(
                image="sslhep/servicex_func_adl_xaod_transformer:develop")

            response = client.post('/servicex/transformation',
                                   json=request,
                                   headers=self.fake_header())
            assert response.status_code == 200
            request_id = response.json['request_id']

            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.did == 'rucio://123-45-678'
            assert saved_obj.did_id == 42
            assert saved_obj.finish_time is None
            assert saved_obj.request_id == request_id
            assert saved_obj.title is None
            assert saved_obj.image == "sslhep/servicex_func_adl_xaod_transformer:develop"
            assert saved_obj.selection == 'test-string'
            assert saved_obj.workers == 10
            assert saved_obj.result_destination == 'object-store'
            assert saved_obj.app_version == "3.14.15"
            assert saved_obj.code_gen_image == 'sslhep/servicex_code_gen_func_adl_xaod:develop'

            setup_queue_calls = [call(request_id), call(request_id+"_errors")]
            mock_rabbit_adaptor.setup_queue.assert_has_calls(setup_queue_calls)
            mock_rabbit_adaptor.setup_exchange.assert_has_calls([
                call('transformation_requests'),
                call('transformation_failures')
            ])

            bind_to_exchange_calls = [
                call(exchange="transformation_requests", queue=request_id),
                call(exchange="transformation_failures", queue=request_id+"_errors"),
            ]

            assert mock_rabbit_adaptor.bind_queue_to_exchange.call_args_list == bind_to_exchange_calls

            mock_dataset_manager_from_did.assert_called_with(ANY,
                                                             db=ANY,
                                                             extras={'requestId': request_id},
                                                             logger=ANY)
            assert mock_dataset_manager_from_did.call_args[0][0].full_did == 'rucio://123-45-678'
            mock_dataset_manager_from_did.return_value.submit_lookup_request.assert_called_with(
                'http://cern.analysis.ch:5000/servicex/internal/transformation/',
                mock_rabbit_adaptor)

    def test_submit_transformation_default_scheme(self, mock_rabbit_adaptor,
                                                  mock_dataset_manager_from_did,
                                                  mock_codegen,
                                                  mock_app_version):
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor,
                                   code_gen_service=mock_codegen)
        mock_dataset_manager_from_did.name = ""
        with client.application.app_context():
            request = self._generate_transformation_request()
            request['did'] = '123-45-678'  # No scheme

            response = client.post('/servicex/transformation',
                                   json=request,
                                   headers=self.fake_header()
                                   )
            assert response.status_code == 200
            request_id = response.json['request_id']
            with client.application.app_context():
                saved_obj = TransformRequest.lookup(request_id)
                assert saved_obj

            mock_dataset_manager_from_did.assert_called_with(ANY,
                                                             db=ANY,
                                                             extras={'requestId': request_id},
                                                             logger=ANY)

            assert mock_dataset_manager_from_did.call_args[0][0].full_did == 'rucio://123-45-678'

            mock_dataset_manager_from_did.return_value.submit_lookup_request.assert_called_with(
                'http://cern.analysis.ch:5000/servicex/internal/transformation/',
                mock_rabbit_adaptor)

    def test_submit_transformation_existing_dataset(self, mocker, mock_rabbit_adaptor,
                                                    mock_dataset_manager_from_did,
                                                    mock_codegen,
                                                    mock_app_version):
        mock_processor = mocker.MagicMock(LookupResultProcessor)

        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor,
                                   lookup_result_processor=mock_processor,
                                   code_gen_service=mock_codegen)

        with client.application.app_context():
            request = self._generate_transformation_request()
            request['did'] = '123-45-678'  # No scheme
            mock_dataset_manager_from_did.return_value.is_lookup_required = False
            mock_dataset_manager_from_did.return_value.is_complete = True
            mock_dataset_manager_from_did.return_value.dataset.id = 256

            response = client.post('/servicex/transformation',
                                   json=request,
                                   headers=self.fake_header()
                                   )
            assert response.status_code == 200
            request_id = response.json['request_id']
            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.did == 'rucio://123-45-678'
            assert saved_obj.did_id == 42

            mock_dataset_manager_from_did.assert_called_with(ANY,
                                                             db=ANY,
                                                             extras={'requestId': request_id},
                                                             logger=ANY)
            assert mock_dataset_manager_from_did.call_args[0][0].full_did == 'rucio://123-45-678'
            mock_dataset_manager_from_did.return_value.submit_lookup_request.assert_not_called()
            mock_dataset_manager_from_did.return_value.publish_files.assert_called_with(
                ANY, mock_processor)

    def test_submit_transformation_incomplete_existing_dataset(self, mocker,
                                                               mock_rabbit_adaptor,
                                                               mock_dataset_manager_from_did,
                                                               mock_codegen,
                                                               mock_app_version):
        mock_processor = mocker.MagicMock(LookupResultProcessor)

        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor,
                                   lookup_result_processor=mock_processor,
                                   code_gen_service=mock_codegen)

        with client.application.app_context():
            request = self._generate_transformation_request()
            request['did'] = '123-45-678'  # No scheme
            mock_dataset_manager_from_did.return_value.is_lookup_required = False
            mock_dataset_manager_from_did.return_value.is_complete = False
            mock_dataset_manager_from_did.return_value.dataset.id = 256

            response = client.post('/servicex/transformation',
                                   json=request,
                                   headers=self.fake_header()
                                   )
            assert response.status_code == 200
            request_id = response.json['request_id']
            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.did == 'rucio://123-45-678'
            assert saved_obj.did_id == 42
            assert saved_obj.status == TransformStatus.pending_lookup

            mock_dataset_manager_from_did.assert_called_with(ANY,
                                                             db=ANY,
                                                             extras={'requestId': request_id},
                                                             logger=ANY)
            assert mock_dataset_manager_from_did.call_args[0][0].full_did == 'rucio://123-45-678'

            mock_dataset_manager_from_did.return_value.submit_lookup_request.assert_not_called()
            mock_dataset_manager_from_did.return_value.publish_files.assert_not_called()

    def test_submit_transformation_with_root_file(self, mock_rabbit_adaptor,
                                                  mock_code_gen_service,
                                                  mock_dataset_manager_from_did,
                                                  mock_app_version):
        mock_code_gen_service.generate_code_for_selection.return_value = ('my-cm',
                                                                          'scala', 'echo',
                                                                          'ssl-hep/func_adl:latest')

        client = self._test_client(
            rabbit_adaptor=mock_rabbit_adaptor, code_gen_service=mock_code_gen_service
        )
        with client.application.app_context():
            request = self._generate_transformation_request()

            response = client.post('/servicex/transformation',
                                   json=request, headers=self.fake_header())

            assert response.status_code == 200
            request_id = response.json['request_id']

            mock_dataset_manager_from_did.assert_called_with(ANY,
                                                             db=ANY,
                                                             extras={'requestId': request_id},
                                                             logger=ANY)
            assert mock_dataset_manager_from_did.call_args[0][0].full_did == 'rucio://123-45-678'

    def test_submit_transformation_file_list(self, mocker,
                                             mock_dataset_manager_from_files,
                                             mock_transform_manager,
                                             mock_codegen,
                                             file_list,
                                             mock_app_version):
        mock_processor = mocker.MagicMock(LookupResultProcessor)
        cfg = {
            'TRANSFORMER_MANAGER_ENABLED': True,
            'TRANSFORMER_X509_SECRET': 'my-x509-secret'
        }

        client = self._test_client(extra_config=cfg,
                                   lookup_result_processor=mock_processor,
                                   transformation_manager=mock_transform_manager,
                                   code_gen_service=mock_codegen)

        with client.application.app_context():
            request = self._generate_transformation_request()
            request['did'] = None
            request['file-list'] = file_list

            mock_dataset_manager_from_files.return_value.is_lookup_required = False

            response = client.post('/servicex/transformation',
                                   json=request, headers=self.fake_header())
            assert response.status_code == 200
            mock_dataset_manager_from_files.return_value.submit_lookup_request.assert_not_called()
            mock_dataset_manager_from_files.return_value.publish_files.assert_called_with(
                ANY, mock_processor)

            request_id = response.json['request_id']
            submitted_request = TransformRequest.lookup(request_id)
            mock_dataset_manager_from_files.assert_called_with(file_list,
                                                               db=ANY,
                                                               extras={'requestId': request_id},
                                                               logger=ANY)

            mock_transform_manager. \
                start_transformers \
                .assert_called_with(ANY, submitted_request)

    def test_submit_transformation_request_bad_image(
        self, mocker, mock_docker_repo_adapter,
            mock_dataset_manager_from_did, mock_codegen
    ):
        mock_docker_repo_adapter.check_image_exists = mocker.Mock(return_value=False)
        client = self._test_client(docker_repo_adapter=mock_docker_repo_adapter,
                                   code_gen_service=mock_codegen)
        request = self._generate_transformation_request()
        request["image"] = "ssl-hep/foo:latest"
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 500
        assert response.json == {"message": "Requested transformer docker image doesn't exist: " + request["image"]}  # noqa: E501

    def test_submit_transformation_request_no_docker_check(
        self, mocker, mock_docker_repo_adapter, mock_dataset_manager_from_did,
            mock_codegen
    ):
        mock_docker_repo_adapter.check_image_exists = mocker.Mock(return_value=False)
        client = self._test_client(
            extra_config={'TRANSFORMER_VALIDATE_DOCKER_IMAGE': False},
            docker_repo_adapter=mock_docker_repo_adapter,
            code_gen_service=mock_codegen
        )
        with client.application.app_context():

            request = self._generate_transformation_request()
            response = client.post('/servicex/transformation',
                                   json=request, headers=self.fake_header())
            assert response.status_code == 200
            mock_docker_repo_adapter.check_image_exists.assert_not_called()

    def test_submit_transformation_with_root_file_selection_error(
        self, mocker, mock_code_gen_service, mock_dataset_manager_from_did
    ):
        mock_code_gen_service.generate_code_for_selection = \
            mocker.Mock(side_effect=ValueError('This is the error message'))
        client = self._test_client(code_gen_service=mock_code_gen_service)
        with client.application.app_context():
            request = self._generate_transformation_request()
            response = client.post('/servicex/transformation',
                                   json=request, headers=self.fake_header())
            assert response.status_code == 500

    def test_submit_transformation_missing_dataset_source(self, client):
        request = self._generate_transformation_request()
        request['did'] = None
        request['file-list'] = []
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400

    def test_submit_transformation_duplicate_dataset_source(self, client):
        request = self._generate_transformation_request()
        request['did'] = "This did"
        request['file-list'] = ["file1.root", "file2.root"]
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400

    def test_submit_transformation_with_object_store(self, mocker,
                                                     mock_dataset_manager_from_did,
                                                     mock_codegen):
        from servicex_app import ObjectStoreManager

        local_config = {
            'OBJECT_STORE_ENABLED': True,
            'MINIO_URL': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'miniouser',
            'MINIO_SECRET_KEY': 'leftfoot1'
        }
        mock_object_store = mocker.MagicMock(ObjectStoreManager)
        client = self._test_client(
            extra_config=local_config,
            object_store=mock_object_store,
            code_gen_service=mock_codegen
        )
        with client.application.app_context():
            request = self._generate_transformation_request(**{
                "result-destination": "object-store",
                "result-format": "parquet"
            })

            response = client.post('/servicex/transformation',
                                   json=request, headers=self.fake_header())
            assert response.status_code == 200
            request_id = response.json['request_id']

            mock_object_store.create_bucket.assert_called_with(request_id)
            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.result_destination == 'object-store'
            assert saved_obj.result_format == 'parquet'

    def test_submit_transformation_default_image(self, mocker, mock_codegen,
                                                 mock_dataset_manager_from_did):
        client = self._test_client(code_gen_service=mock_codegen)
        with client.application.app_context():
            request = self._generate_transformation_request(**{
                "result-destination": "object-store",
                "result-format": "parquet",
                "selection": "(great (LISP is))"
            })

            response = client.post('/servicex/transformation',
                                   json=request, headers=self.fake_header())
            assert response.status_code == 200
            request_id = response.json['request_id']

            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.image == 'ssl-hep/func_adl:latest'

    def test_submit_transformation_provided_image(self, mocker, mock_codegen,
                                                  mock_dataset_manager_from_did):
        client = self._test_client(code_gen_service=mock_codegen)
        with client.application.app_context():
            request = self._generate_transformation_request(**{
                "result-destination": "object-store",
                "result-format": "parquet",
                "selection": "(great (LISP is))",
                "image": "my-image:latest"
            })

            response = client.post('/servicex/transformation',
                                   json=request, headers=self.fake_header())
            assert response.status_code == 200
            request_id = response.json['request_id']

            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.image == 'my-image:latest'

    def test_submit_transformation_auth_enabled(
        self, mock_jwt_extended, mock_requesting_user,
            mock_dataset_manager_from_did, mock_codegen
    ):
        client = self._test_client(extra_config={'ENABLE_AUTH': True},
                                   code_gen_service=mock_codegen)
        with client.application.app_context():

            response = client.post('/servicex/transformation',
                                   json=self._generate_transformation_request(),
                                   headers=self.fake_header())
            assert response.status_code == 200
            request_id = response.json['request_id']

            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.submitted_by == mock_requesting_user.id

    def test_submit_transformation_with_title(self, mock_dataset_manager_from_did,
                                              mock_codegen):
        client = self._test_client(code_gen_service=mock_codegen)
        with client.application.app_context():
            title = "Things Fall Apart"
            request = self._generate_transformation_request(title=title)
            response = client.post('/servicex/transformation',
                                   json=request, headers=self.fake_header())
            assert response.status_code == 200
            request_id = response.json['request_id']
            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.title == title
