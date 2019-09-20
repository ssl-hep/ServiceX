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
from tests.resources.resource_test_base import ResourceTestBase


class TestFilesetComplete(ResourceTestBase):
    def test_put_fileset_complete(self, mocker,  mock_rabbit_adaptor):
        import servicex
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'return_request',
            return_value=self._generate_transform_request())

        mock_transform_request_update = mocker.patch.object(
            servicex.models.TransformRequest,
            'update_request')

        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)
        response = client.put('/servicex/transformation/1234/complete',
                              json={
                                  'files': 17,
                                  'files-skipped': 2,
                                  'total-events': 1024,
                                  'total-bytes': 2046,
                                  'elapsed-time': 42
                              })
        assert response.status_code == 200
        mock_transform_request_read.assert_called_with('1234')

        # TODO: Figure out how to verify the update mock
        mock_transform_request_update.assert_called()
