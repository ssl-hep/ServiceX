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

from servicex.models import TransformRequest
from tests.resource_test_base import ResourceTestBase


class TestSubmitTransformationRequest(ResourceTestBase):

    def test_submit_transformation_request_bad(self, mocker, mock_rabbit_adaptor):
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)
        response = client.post('/servicex/transformation',
                               json={'timestamp': '20190101'})
        assert response.status_code == 400

    @staticmethod
    def _generate_transformation_request():
        return {'did': '123-45-678',
                'columns': "e.e, e.p",
                'image': 'ssl-hep/foo:latest',
                'result-destination': 'kafka',
                'kafka': {
                    'broker': 'ssl.hep.kafka:12332'
                },
                'chunk-size': 500,
                'workers': 10}

    def test_submit_transformation_bad_result_dest(self, mocker, mock_rabbit_adaptor):
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)
        request = self._generate_transformation_request()
        request['result-destination'] = 'foo'
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400

    def test_submit_transformation_bad_result_format(self, mocker, mock_rabbit_adaptor):
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)
        request = self._generate_transformation_request()
        request['result-format'] = 'foo'
        response = client.post('/servicex/transformation', json=request)
        assert response.status_code == 400

    def test_submit_transformation_request_throws_exception(self, mocker, mock_rabbit_adaptor):
        mock_rabbit_adaptor.setup_queue = mocker.Mock(side_effect=Exception('Test'))
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)

        response = client.post('/servicex/transformation',
                               json=self._generate_transformation_request())
        assert response.status_code == 500
        assert response.json == {"message": "Something went wrong"}

    def test_submit_transformation(self, mocker, mock_rabbit_adaptor):
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)
        response = client.post('/servicex/transformation',
                               json=self._generate_transformation_request())

        assert response.status_code == 200

        request_id = response.json['request_id']

        with client.application.app_context():
            saved_obj = TransformRequest.return_request(request_id)
            assert saved_obj
            assert saved_obj.did == '123-45-678'
            assert saved_obj.request_id == request_id
            assert saved_obj.columns == "e.e, e.p"
            assert saved_obj.image == 'ssl-hep/foo:latest'
            assert saved_obj.chunk_size == 500
            assert saved_obj.workers == 10
            assert saved_obj.result_destination == 'kafka'
            assert saved_obj.kafka_broker == "ssl.hep.kafka:12332"

        setup_queue_calls = [call(request_id), call(request_id+"_errors")]
        mock_rabbit_adaptor.setup_queue.assert_has_calls(setup_queue_calls)
        mock_rabbit_adaptor.bind_queue_to_exchange.assert_called_with(
                exchange="transformation_requests",
                queue=request_id)

        service_endpoint = "http://cern.analysis.ch:5000/servicex/transformation/" + request_id
        mock_rabbit_adaptor. \
            basic_publish.assert_called_with(exchange='',
                                             routing_key='did_requests',
                                             body=json.dumps(
                                                 {
                                                     "request_id": request_id,
                                                     "did": "123-45-678",
                                                     "service-endpoint": service_endpoint}
                                             ))

    def test_submit_transformation_with_object_store(self, mocker, mock_rabbit_adaptor):
        from servicex import ObjectStoreManager

        local_config = {
            'OBJECT_STORE_ENABLED': True,
            'MINIO_URL': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'miniouser',
            'MINIO_SECRET_KEY': 'leftfoot1'
        }

        transformation_request = {'did': '123-45-678',
                                  'columns': "e.e, e.p",
                                  'image': 'ssl-hep/foo:latest',
                                  'result-destination': 'object-store',
                                  'result-format': 'parquet',
                                  'chunk-size': 500,
                                  'workers': 10}

        mock_object_store = mocker.MagicMock(ObjectStoreManager)
        client = self._test_client(additional_config=local_config,
                                   rabbit_adaptor=mock_rabbit_adaptor,
                                   object_store=mock_object_store)
        response = client.post('/servicex/transformation',
                               json=transformation_request)
        assert response.status_code == 200

        request_id = response.json['request_id']

        mock_object_store.create_bucket.assert_called_with(request_id)
        with client.application.app_context():
            saved_obj = TransformRequest.return_request(request_id)
            assert saved_obj
            assert saved_obj.result_destination == 'object-store'
            assert saved_obj.result_format == 'parquet'
