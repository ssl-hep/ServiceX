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
import pytest
from unittest.mock import MagicMock

from servicex_app.docker_repo_adapter import DockerRepoAdapter


@pytest.fixture
def mock_subprocess_success(mocker):
    """Mock subprocess.run to return success (returncode=0)."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    return mocker.patch("servicex_app.docker_repo_adapter.subprocess.run", return_value=mock_result)


@pytest.fixture
def mock_subprocess_failure(mocker):
    """Mock subprocess.run to return failure (returncode=1)."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    return mocker.patch("servicex_app.docker_repo_adapter.subprocess.run", return_value=mock_result)


@pytest.fixture(autouse=True)
def mock_current_app(mocker):
    """Automatically mock current_app for all tests in this class."""
    mock_app = MagicMock()
    mocker.patch("servicex_app.docker_repo_adapter.current_app", new=mock_app)
    return mock_app


class TestDockerRepoAdapter:
    def test_check_image_exists(self, mock_subprocess_success):
        docker = DockerRepoAdapter()
        result = docker.check_image_exists("foo/bar:baz")
        assert result

    def test_check_image_exists_not_there(self, mock_subprocess_failure):
        docker = DockerRepoAdapter()
        result = docker.check_image_exists("foo/bar:baz")
        assert not result

    def test_check_image_exists_invalid_name(self, mock_subprocess_failure):
        docker = DockerRepoAdapter()

        assert not docker.check_image_exists("foobar:baz")
        assert not docker.check_image_exists("foo/barbaz")
        assert not docker.check_image_exists("foobarbaz")
        assert not docker.check_image_exists("")

    def test_get_image_by_tag_invalid_registry(self, mock_subprocess_failure):
        docker = DockerRepoAdapter()
        result = docker.check_image_exists("invalid.registry.com/foo/bar:baz")
        assert not result
