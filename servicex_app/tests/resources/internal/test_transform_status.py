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


class TestTransformStatusInternal(ResourceTestBase):
    def test_post_status(self, mocker, client):
        from servicex.models import TransformRequest
        mock_request = self._generate_transform_request()
        mock_request.save_to_db = mocker.Mock()
        mocker.patch.object(
            TransformRequest,
            'lookup',
            return_value=mock_request)

        response = client.post('/servicex/internal/transformation/1234/status',
                               json={
                                   'timestamp': '2019-09-18T16:15:09.457481',
                                   'severity': "info",
                                   'info': 'Just testing'
                               })

        assert response.status_code == 200
        mock_request.save_to_db.assert_not_called()

    def test_post_status_fatal(self, mocker, client):
        from servicex.models import TransformRequest
        mock_request = self._generate_transform_request()
        mock_request.save_to_db = mocker.Mock()
        mocker.patch.object(
            TransformRequest,
            'lookup',
            return_value=mock_request)

        response = client.post('/servicex/internal/transformation/1234/status',
                               json={
                                   'timestamp': '2019-09-18T16:15:09.457481',
                                   'severity': "fatal",
                                   'info': 'Just testing'
                               })

        assert response.status_code == 200
        assert mock_request.finish_time is not None
        mock_request.save_to_db.assert_called()

    def test_post_status_bad_data(self, client):
        response = client.post('/servicex/internal/transformation/1234/status',
                               json={'foo': 'bar'})
        assert response.status_code == 400
