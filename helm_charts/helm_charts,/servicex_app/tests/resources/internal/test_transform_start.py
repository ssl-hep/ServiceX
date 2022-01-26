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
from tests.resource_test_base import ResourceTestBase


class TestTransformationStart(ResourceTestBase):
    def test_transform_start(self, mocker):
        import servicex
        from servicex.transformer_manager import TransformerManager
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.launch_transformer_jobs = mocker.Mock()
        mock_request = self._generate_transform_request()
        mock_request.save_to_db = mocker.Mock()
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=mock_request)

        cfg = {
            'TRANSFORMER_MANAGER_ENABLED': True,
            'TRANSFORMER_X509_SECRET': 'my-x509-secret'
        }
        client = self._test_client(
            extra_config=cfg, transformation_manager=mock_transformer_manager
        )

        response = client.post('/servicex/internal/transformation/1234/start',
                               json={
                                   'info': {
                                       'max-event-size': 4567}
                               })
        assert response.status_code == 200
        mock_transform_request_read.assert_called_with('1234')

        mock_transformer_manager. \
            launch_transformer_jobs \
            .assert_called_with(image='ssl-hep/foo:latest',
                                request_id='BR549',
                                workers=42,
                                generated_code_cm=None,
                                rabbitmq_uri='amqp://trans.rabbit',
                                namespace='my-ws',
                                result_destination=None,
                                result_format='arrow',
                                x509_secret='my-x509-secret')
        mock_request.save_to_db.assert_called()

    def test_transform_start_no_kubernetes(self, mocker, mock_rabbit_adaptor):
        import servicex
        from servicex.transformer_manager import TransformerManager
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.launch_transformer_jobs = mocker.Mock()
        mock_request = self._generate_transform_request()
        mock_request.save_to_db = mocker.Mock()

        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=mock_request)

        client = self._test_client(
            {
                'TRANSFORMER_MANAGER_ENABLED': False
            },
            mock_transformer_manager,
            mock_rabbit_adaptor)

        response = client.post('/servicex/internal/transformation/1234/start',
                               json={'max-event-size': 4567})
        assert response.status_code == 200
        mock_transform_request_read.assert_called_with('1234')

        mock_transformer_manager.\
            launch_transformer_jobs.assert_not_called()

        mock_request.save_to_db.assert_called()

    def test_stopped(self, client, mocker):
        import servicex
        from servicex.transformer_manager import TransformerManager
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.launch_transformer_jobs = mocker.Mock()
        mock_request = self._generate_transform_request()
        mock_request.save_to_db = mocker.Mock()
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=mock_request)

        mock_request.status = "Canceled"
        response = client.post('/servicex/internal/transformation/1234/start',
                               json={'max-event-size': 4567})
        assert response.status_code == 409
        mock_transform_request_read.assert_called_with('1234')
