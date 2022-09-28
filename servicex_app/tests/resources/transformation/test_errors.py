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
from servicex.models import DatasetFile, FileStatus


class TestTransformErrors(ResourceTestBase):
    def test_get_errors(self, mocker, client):
        import servicex

        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=self._generate_transform_request())

        file_error_result = [
            (DatasetFile(
                paths=["/foo/bar1.root", "/foo/bar2.root"],
                file_events=42
            ), FileStatus(
                pod_name='openthepodhal',
                info="sorry I can't"
            ))
        ]
        mock_transform_errors = mocker.patch.object(
            servicex.models.FileStatus,
            'failures_for_request',
            return_value=file_error_result)

        response = client.get('/servicex/transformation/1234/errors')
        assert response.status_code == 200
        assert response.json == {'errors': [
            {'pod-name': 'openthepodhal',
             'file': '/foo/bar1.root',
             'events': 42,
             'info': "sorry I can't"
             }
        ]}

        mock_transform_request_read.assert_called_with("1234")
        mock_transform_errors.assert_called_with("1234")

    def test_get_errors_404(self, mocker, client):
        import servicex

        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=None)

        response = client.get('/servicex/transformation/1234/errors')
        assert response.status_code == 404

        mock_transform_request_read.assert_called_with("1234")
