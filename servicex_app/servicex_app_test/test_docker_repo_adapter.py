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
from servicex_app.docker_repo_adapter import DockerRepoAdapter


class TestDockerRepoAdapter:
    def test_check_image_exists(self, mocker):
        import requests
        from unittest.mock import MagicMock

        mock_response = mocker.Mock()
        mock_get = mocker.patch.object(requests, "get", return_value=mock_response)
        mock_response.status_code = 200
        mock_response.json = mocker.Mock(
            return_value={"last_updated": "2020-07-22T21:13:55.317762Z"}
        )

        # Mock the Flask logger at the module level with a new mock object
        mock_app = MagicMock()
        mocker.patch("servicex_app.docker_repo_adapter.current_app", new=mock_app)

        docker = DockerRepoAdapter()
        result = docker.check_image_exists("foo/bar:baz")
        assert result

        mock_get.assert_called_with(
            "https://hub.docker.com/v2/repositories/foo/bar/tags/baz",
            timeout=(0.5, None),
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

    def test_check_image_exists_gitlab_cern(self, mocker):
        import requests
        from unittest.mock import MagicMock

        # Mock the repository listing response
        mock_repos_response = mocker.Mock()
        mock_repos_response.status_code = 200
        mock_repos_response.json = mocker.Mock(
            return_value=[{"id": 123, "path": "atlas/myimage"}]
        )

        # Mock the tag response
        mock_tag_response = mocker.Mock()
        mock_tag_response.status_code = 200
        mock_tag_response.json = mocker.Mock(
            return_value={"last_updated": "2024-01-15T10:30:00.000000Z"}
        )

        # Set up mock to return different responses for different URLs
        def mock_get(url, timeout=None):
            if "registry/repositories" in url and "/tags/" not in url:
                return mock_repos_response
            else:
                return mock_tag_response

        mocker.patch.object(requests, "get", side_effect=mock_get)

        # Mock the Flask logger at the module level with a new mock object
        mock_app = MagicMock()
        mocker.patch("servicex_app.docker_repo_adapter.current_app", new=mock_app)

        docker = DockerRepoAdapter()
        result = docker.check_image_exists(
            "gitlab-registry.cern.ch/atlas/myimage:latest"
        )
        assert result

    def test_check_image_exists_gitlab_cern_not_found(self, mocker):
        import requests

        # Mock the repository listing response with empty list
        mock_repos_response = mocker.Mock()
        mock_repos_response.status_code = 200
        mock_repos_response.json = mocker.Mock(return_value=[])

        mocker.patch.object(requests, "get", return_value=mock_repos_response)

        docker = DockerRepoAdapter()
        result = docker.check_image_exists(
            "gitlab-registry.cern.ch/atlas/myimage:latest"
        )
        assert not result

    def test_check_image_exists_gitlab_cern_tag_not_found(self, mocker):
        import requests

        # Mock the repository listing response
        mock_repos_response = mocker.Mock()
        mock_repos_response.status_code = 200
        mock_repos_response.json = mocker.Mock(
            return_value=[{"id": 123, "path": "atlas/myimage"}]
        )

        # Mock the tag response as 404
        mock_tag_response = mocker.Mock()
        mock_tag_response.status_code = 404

        # Set up mock to return different responses for different URLs
        def mock_get(url, timeout=None):
            if "registry/repositories" in url and "/tags/" not in url:
                return mock_repos_response
            else:
                return mock_tag_response

        mocker.patch.object(requests, "get", side_effect=mock_get)

        docker = DockerRepoAdapter()
        result = docker.check_image_exists(
            "gitlab-registry.cern.ch/atlas/myimage:notfound"
        )
        assert not result

    def test_get_image_by_tag_invalid_registry(self, mocker):
        docker = DockerRepoAdapter()
        result = docker.check_image_exists("invalid.registry.com/foo/bar:baz")
        assert not result

    def test_parse_docker_registry_with_port(self, mocker):
        docker = DockerRepoAdapter()
        registry = docker._parse_docker_registry("localhost:5000/myrepo/myimage:latest")
        assert registry == "localhost:5000"

    def test_parse_docker_registry_with_domain(self, mocker):
        docker = DockerRepoAdapter()
        registry = docker._parse_docker_registry(
            "registry.example.com/myrepo/myimage:latest"
        )
        assert registry == "registry.example.com"

    def test_parse_docker_registry_docker_io(self, mocker):
        docker = DockerRepoAdapter()
        registry = docker._parse_docker_registry("foo/bar:latest")
        assert registry == "docker.io"

    def test_parse_docker_registry_with_digest(self, mocker):
        docker = DockerRepoAdapter()
        registry = docker._parse_docker_registry(
            "registry.example.com/myrepo/myimage@sha256:abc123"
        )
        assert registry == "registry.example.com"
