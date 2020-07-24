# Copyright (c) 2020, IRIS-HEP
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
from servicex.docker_repo_adapter import DockerRepoAdapter


class TestDockerRepoAdapter:
    def test_check_image_exists(self, mocker):
        import requests
        mock_response = mocker.Mock()
        mock_get = mocker.patch.object(requests, "get", return_value=mock_response)
        mock_response.status_code = 200
        mock_response.json = mocker.Mock(return_value={
            'last_updated': '2020-07-22T21:13:55.317762Z'})
        docker = DockerRepoAdapter()
        result = docker.check_image_exists("foo/bar:baz")
        assert result

        mock_get.assert_called_with(
            'https://hub.docker.com/v2/repositories/foo/bar/tags/baz'
        )

    def test_check_image_exists_not_there(self, mocker):
        import requests
        mock_response = mocker.Mock()
        mocker.patch.object(requests, "get", return_value=mock_response)
        mock_response.status_code = 404
        docker = DockerRepoAdapter()
        result = docker.check_image_exists("foo/bar:baz")
        assert not result

    def test_check_image_exists_invalid_name(self, mocker):
        import requests
        mock_response = mocker.Mock()
        mocker.patch.object(requests, "get", return_value=mock_response)
        mock_response.status_code = 404
        docker = DockerRepoAdapter()
        result = docker.check_image_exists("foobar:baz")
        assert not result

        assert not docker.check_image_exists("foo/barbaz")
        assert not docker.check_image_exists("foobarbaz")
        assert not docker.check_image_exists("")
