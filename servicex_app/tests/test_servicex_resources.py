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

from pytest import fixture

from servicex import create_app
from servicex.models import TransformRequest
from servicex.rabbit_adaptor import RabbitAdaptor


def _app_config():
    return {
        'TESTING': True,
        'RABBIT_MQ_URL': 'amqp://foo.com',
        'SQLALCHEMY_DATABASE_URI': "sqlite:///:memory:",
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'TRANSFORMER_RABBIT_MQ_URL': "amqp://trans.rabbit",
        'TRANSFORMER_NAMESPACE': "my-ws",
        'TRANSFORMER_MANAGER_ENABLED': False,
        'ADVERTISED_HOSTNAME': 'cern.analysis.ch:5000'
    }


def _generate_transform_request():
    transform_request = TransformRequest()
    transform_request.chunk_size = 1000
    transform_request.workers = 42
    return transform_request


class TestServiceXResources:

    @staticmethod
    def _test_client(mocker, additional_config=None, transformation_manager=None, rabbit_adaptor=None):
        config = _app_config()
        config['TRANSFORMER_MANAGER_ENABLED'] = False
        config['TRANSFORMER_MANAGER_MODE'] = 'external'

        if additional_config:
            config.update(additional_config)

        app = create_app(config, transformation_manager, rabbit_adaptor)

        return app.test_client()

    @fixture
    def mock_rabbit_adaptor(self, mocker):
        return mocker.MagicMock(RabbitAdaptor)

    def test_submit_transformation_request_bad(self, mocker, mock_rabbit_adaptor):
        client = TestServiceXResources._test_client(mocker, rabbit_adaptor=mock_rabbit_adaptor)
        response = client.post('/servicex/transformation',
                               json={'foo': 'bar'})
        assert response.status_code == 400

    @staticmethod
    def _generate_transformation_request():
        return {'did': '123-45-678',
                'columns': "e.e, e.p",
                'image': 'ssl-hep/foo:latest',
                'kafka-broker': 'ssl.hep.kafka:12332',
                'chunk-size': 500,
                'workers': 10}

    def test_submit_transformation_request_throws_exception(self, mocker, mock_rabbit_adaptor):
        mock_rabbit_adaptor.setup_queue = mocker.Mock(side_effect=Exception('Test'))
        client = TestServiceXResources._test_client(mocker, rabbit_adaptor=mock_rabbit_adaptor)

        response = client.post('/servicex/transformation',
                               json=self._generate_transformation_request())
        assert response.status_code == 500
        assert response.json == {"message": "Something went wrong"}

    def test_submit_transformation(self, mocker, mock_rabbit_adaptor):
        client = TestServiceXResources._test_client(mocker, rabbit_adaptor=mock_rabbit_adaptor)
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
            assert not saved_obj.messaging_backend
            assert saved_obj.kafka_broker == "ssl.hep.kafka:12332"
        mock_rabbit_adaptor.setup_queue.assert_called_with(request_id)
        mock_rabbit_adaptor.bind_queue_to_exchange.assert_called_with(
                exchange="transformation_requests",
                queue=request_id)
        mock_rabbit_adaptor. \
            basic_publish.assert_called_with(exchange='',
                                             routing_key='did_requests',
                                             body=json.dumps(
                                                 {
                                                     "request_id": request_id,
                                                     "did": "123-45-678",
                                                     "service-endpoint": "http://cern.analysis.ch:5000/servicex/transformation/" + request_id}
                                             ))

    def test_transform_start(self, mocker, mock_rabbit_adaptor):
        import servicex
        from servicex.transformer_manager import TransformerManager
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.launch_transformer_jobs = mocker.Mock()
        mocker.patch('servicex.transformer_manager.TransformerManager', return_value= mock_transformer_manager)
        mock_transform_request_read = mocker.Mock(return_value=_generate_transform_request())
        servicex.models.TransformRequest.return_request = mock_transform_request_read

        client = TestServiceXResources._test_client(mocker,
                                                    {
                                                        'TRANSFORMER_MANAGER_ENABLED': True
                                                    },
                                                    mock_transformer_manager,
                                                    mock_rabbit_adaptor)

        response = client.post('/servicex/transformation/1234/start')
        assert response.status_code == 200
        mock_transform_request_read.assert_called_with('1234')

        mock_transformer_manager.\
            launch_transformer_jobs.assert_called_with('1234', 42,
                                                       1000, 'amqp://trans.rabbit',
                                                       'my-ws')

    def test_transform_start_no_kubernetes(self, mocker, mock_rabbit_adaptor):
        import servicex
        from servicex.transformer_manager import TransformerManager
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.launch_transformer_jobs = mocker.Mock()
        mocker.patch('servicex.transformer_manager.TransformerManager',
                     return_value= mock_transformer_manager)
        mock_transform_request_read = mocker.Mock(
            return_value=_generate_transform_request())
        servicex.models.TransformRequest.return_request = mock_transform_request_read

        client = TestServiceXResources._test_client(mocker,
                                                    {
                                                        'TRANSFORMER_MANAGER_ENABLED': False
                                                    },
                                                    mock_transformer_manager,
                                                    mock_rabbit_adaptor)

        response = client.post('/servicex/transformation/1234/start')
        assert response.status_code == 200
        mock_transform_request_read.assert_called_with('1234')

        mock_transformer_manager.\
            launch_transformer_jobs.assert_not_called()
