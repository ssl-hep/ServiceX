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
import pkg_resources

from servicex.resources.servicex_resource import ServiceXResource
from tests.resource_test_base import ResourceTestBase


class TestServiceXResource(ResourceTestBase):
    def test_get_app_version_no_servicex_app(self, mocker):
        mock_get_distribution = mocker.patch(
            "servicex.resources.servicex_resource.pkg_resources.get_distribution",
            side_effect=pkg_resources.DistributionNotFound(None, None))

        version = ServiceXResource._get_app_version()

        mock_get_distribution.assert_called_with("servicex_app")
        assert version == 'develop'

    def test_get_requesting_user_no_auth(self, client):
        with client.application.app_context():
            assert ServiceXResource.get_requesting_user() is None

    def test_get_requesting_user_with_auth(self, mock_requesting_user):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            assert ServiceXResource.get_requesting_user() == mock_requesting_user
