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
import json
from unittest.mock import call

from flask import current_app

from servicex import LookupResultProcessor
from servicex.models import TransformRequest
from tests.resource_test_base import ResourceTestBase


class TestSubmitTransformationRequest(ResourceTestBase):

    @staticmethod
    def _generate_transformation_request(**kwargs):
        request = {
            'did': 'rucio://123-45-678',
            'columns': "e.e, e.p",
            'result-destination': 'object-store',
            'workers': 10
        }
        request.update(kwargs)
        return request

    @staticmethod
    def _generate_transformation_request_xAOD_root_file():
        return {
            'did': '123-45-678',
            'selection': "test-string",
            'image': 'ssl-hep/func_adl:latest',
            'result-destination': 'object-store',
            'result-format': 'root-file',
            'workers': 10
        }

    def test_submit_transformation_request_bad(self, client):
        resp = client.post('/servicex/transformation', json={'timestamp': '20190101'})
        assert resp.status_code == 400

    def test_submit_transformation_bad_result_dest(self, client):
        request = self._generate_transformation_request()
        request['result-destination'] = 'foo'
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400

    def test_submit_transformation_bad_wrong_dest_for_format(self, client):
        request = self._generate_transformation_request()
        request['result-format'] = 'root-file'
        request['result-destination'] = 'minio'
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400

    def test_submit_transformation_bad_result_format(self, client):
        request = self._generate_transformation_request()
        request['result-format'] = 'foo'
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400

    def test_submit_transformation_bad_workflow(self, client):
        request = self._generate_transformation_request(columns=None, selection=None)
        r = client.post('/servicex/transformation', json=request)
        assert r.status_code == 400

    def test_submit_transformation_bad_did_scheme(self, client):
        request = self._generate_transformation_request(did='foobar://my-did')
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400
        assert "DID scheme is not supported" in response.json["message"]

    def test_submit_transformation_request_throws_exception(
        self, mocker, mock_rabbit_adaptor
    ):
        mock_rabbit_adaptor.setup_queue = mocker.Mock(side_effect=Exception('Test'))
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)

        response = client.post('/servicex/transformation',
                               json=self._generate_transformation_request())
        assert response.status_code == 503
        assert response.json == {"message": "Error setting up transformer queues"}

    def test_submit_transformation(self, mock_rabbit_adaptor, mock_app_version):
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)
        request = self._generate_transformation_request()

        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 200
        request_id = response.json['request_id']
        with client.application.app_context():
            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.did == 'rucio://123-45-678'
            assert saved_obj.finish_time is None
            assert saved_obj.request_id == request_id
            assert saved_obj.title is None
            assert saved_obj.columns == "e.e, e.p"
            assert saved_obj.image == current_app.config["TRANSFORMER_DEFAULT_IMAGE"]
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

        service_endpoint = \
            "http://cern.analysis.ch:5000/servicex/internal/transformation/" + \
            request_id
        publish_body = {
            "request_id": request_id,
            "did": "123-45-678",
            "service-endpoint": service_endpoint
        }
        mock_rabbit_adaptor.basic_publish.assert_called_with(
            exchange='',
            routing_key='rucio_did_requests',
            body=json.dumps(publish_body)
        )

    def test_submit_transformation_default_scheme(self, mock_rabbit_adaptor, mock_app_version):
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)
        request = self._generate_transformation_request()
        request['did'] = '123-45-678'  # No scheme

        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 200
        request_id = response.json['request_id']
        with client.application.app_context():
            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.did == 'rucio://123-45-678'

        service_endpoint = \
            "http://cern.analysis.ch:5000/servicex/internal/transformation/" + \
            request_id
        publish_body = {
            "request_id": request_id,
            "did": "123-45-678",
            "service-endpoint": service_endpoint
        }
        mock_rabbit_adaptor.basic_publish.assert_called_with(
            exchange='',
            routing_key='rucio_did_requests',
            body=json.dumps(publish_body)
        )

    def test_submit_transformation_with_root_file(
        self, mocker, mock_rabbit_adaptor, mock_code_gen_service, mock_app_version
    ):
        mock_code_gen_service.generate_code_for_selection.return_value = 'my-cm'
        request = self._generate_transformation_request_xAOD_root_file()

        client = self._test_client(
            rabbit_adaptor=mock_rabbit_adaptor, code_gen_service=mock_code_gen_service
        )

        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 200
        request_id = response.json['request_id']

        with client.application.app_context():
            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.did == 'rucio://123-45-678'
            assert saved_obj.request_id == request_id
            assert saved_obj.columns is None
            assert saved_obj.selection == 'test-string'
            assert saved_obj.image == 'ssl-hep/func_adl:latest'
            assert saved_obj.workers == 10
            assert saved_obj.result_destination == 'object-store'
            assert saved_obj.result_format == 'root-file'
            assert saved_obj.generated_code_cm == 'my-cm'
            assert saved_obj.app_version == "3.14.15"
            assert saved_obj.code_gen_image == 'sslhep/servicex_code_gen_func_adl_xaod:develop'

        setup_queue_calls = [call(request_id), call(request_id+"_errors")]
        mock_rabbit_adaptor.setup_queue.assert_has_calls(setup_queue_calls)

        bind_to_exchange_calls = [
            call(exchange="transformation_requests", queue=request_id),
            call(exchange="transformation_failures", queue=request_id+"_errors"),
        ]

        assert mock_rabbit_adaptor.bind_queue_to_exchange.call_args_list == bind_to_exchange_calls

        service_endpoint = \
            "http://cern.analysis.ch:5000/servicex/internal/transformation/" + \
            request_id

        mock_rabbit_adaptor. \
            basic_publish.assert_called_with(exchange='',
                                             routing_key='rucio_did_requests',
                                             body=json.dumps(
                                                 {
                                                     "request_id": request_id,
                                                     "did": "123-45-678",
                                                     "service-endpoint": service_endpoint}
                                             ))

    def test_submit_transformation_file_list(self, mocker):
        from servicex.transformer_manager import TransformerManager
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.launch_transformer_jobs = mocker.Mock()

        request = self._generate_transformation_request()
        request['did'] = None
        request['file-list'] = ["file1", "file2"]

        mock_processor = mocker.MagicMock(LookupResultProcessor)
        cfg = {
            'TRANSFORMER_MANAGER_ENABLED': True,
            'TRANSFORMER_X509_SECRET': 'my-x509-secret'
        }

        client = self._test_client(extra_config=cfg,
                                   lookup_result_processor=mock_processor,
                                   transformation_manager=mock_transformer_manager)

        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 200
        request_id = response.json['request_id']

        mock_processor.add_file_to_dataset.assert_called()
        add_file_calls = mock_processor.add_file_to_dataset.call_args_list
        assert mock_processor.add_file_to_dataset.call_count == 2
        assert add_file_calls[0][0][1].paths == 'file1'
        assert add_file_calls[1][0][1].paths == 'file2'

        mock_processor.report_fileset_complete.assert_called()
        fileset_complete_call = mock_processor.report_fileset_complete.call_args
        assert fileset_complete_call[1]['num_files'] == 2
        with client.application.app_context():
            submitted_request = TransformRequest.lookup(request_id)

            mock_transformer_manager. \
                launch_transformer_jobs \
                .assert_called_with(image=submitted_request.image,
                                    request_id=submitted_request.request_id,
                                    workers=submitted_request.workers,
                                    generated_code_cm=submitted_request.generated_code_cm,
                                    rabbitmq_uri='amqp://trans.rabbit',
                                    namespace='my-ws',
                                    result_destination=submitted_request.result_destination,
                                    result_format=submitted_request.result_format,
                                    x509_secret='my-x509-secret')

    def test_submit_transformation_request_bad_image(
        self, mocker, mock_docker_repo_adapter
    ):
        mock_docker_repo_adapter.check_image_exists = mocker.Mock(return_value=False)
        client = self._test_client(docker_repo_adapter=mock_docker_repo_adapter)
        request = self._generate_transformation_request()
        request["image"] = "ssl-hep/foo:latest"
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400
        assert response.json == {"message": "Requested transformer docker image doesn't exist: " + request["image"]}  # noqa: E501

    def test_submit_transformation_request_no_docker_check(
        self, mocker, mock_docker_repo_adapter
    ):
        mock_docker_repo_adapter.check_image_exists = mocker.Mock(return_value=False)
        client = self._test_client(
            extra_config={'TRANSFORMER_VALIDATE_DOCKER_IMAGE': False},
            docker_repo_adapter=mock_docker_repo_adapter,
        )
        request = self._generate_transformation_request()
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 200
        mock_docker_repo_adapter.check_image_exists.assert_not_called()

    def test_submit_transformation_with_root_file_selection_error(
        self, mocker, mock_code_gen_service
    ):
        mock_code_gen_service.generate_code_for_selection = \
            mocker.Mock(side_effect=ValueError('This is the error message'))
        request = self._generate_transformation_request_xAOD_root_file()
        client = self._test_client(code_gen_service=mock_code_gen_service)
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400

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

    def test_submit_transformation_with_object_store(self, mocker):
        from servicex import ObjectStoreManager

        local_config = {
            'OBJECT_STORE_ENABLED': True,
            'MINIO_URL': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'miniouser',
            'MINIO_SECRET_KEY': 'leftfoot1'
        }
        mock_object_store = mocker.MagicMock(ObjectStoreManager)
        client = self._test_client(
            extra_config=local_config,
            object_store=mock_object_store
        )
        request = self._generate_transformation_request(**{
            "result-destination": "object-store",
            "result-format": "parquet"
        })

        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 200
        request_id = response.json['request_id']

        mock_object_store.create_bucket.assert_called_with(request_id)
        with client.application.app_context():
            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.result_destination == 'object-store'
            assert saved_obj.result_format == 'parquet'

    def test_submit_transformation_auth_enabled(
        self, mock_jwt_extended, mock_requesting_user
    ):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        response = client.post('/servicex/transformation',
                               json=self._generate_transformation_request())
        assert response.status_code == 200
        request_id = response.json['request_id']

        with client.application.app_context():
            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.submitted_by == mock_requesting_user.id

    def test_submit_transformation_with_title(self, client):
        title = "Things Fall Apart"
        request = self._generate_transformation_request(title=title)
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 200
        request_id = response.json['request_id']
        with client.application.app_context():
            saved_obj = TransformRequest.lookup(request_id)
            assert saved_obj
            assert saved_obj.title == title
