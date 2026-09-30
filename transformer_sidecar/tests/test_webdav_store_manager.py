# Copyright (c) 2025, IRIS-HEP
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
import base64
import os

import pytest

from transformer_sidecar.object_store_manager import ObjectStoreError
from transformer_sidecar.webdav_store_manager import (
    WebDavStoreError,
    WebDavStoreManager,
)

WEBDAV_ENV = {
    "WEBDAV_URL": "http://webdav:80",
    "WEBDAV_ROOT": "servicex",
    "WEBDAV_USERNAME": "user",
    "WEBDAV_PASSWORD": "shhh",
}


@pytest.fixture
def mock_pool_manager(mocker):
    return mocker.patch("transformer_sidecar.webdav_store_manager.urllib3.PoolManager")


def response(status):
    class _Response:
        def __init__(self, status):
            self.status = status

    return _Response(status)


@pytest.fixture
def result_file(tmp_path):
    path = tmp_path / "result.parquet"
    path.write_bytes(b"some columns")
    return path


class TestWebDavStoreManager:
    def test_init(self, mock_pool_manager):
        store = WebDavStoreManager(
            "http://localhost:8080/", username="foo", password="bar", root="/sx/"
        )
        assert store.url == "http://localhost:8080"
        assert store.root == "sx"
        expected = base64.b64encode(b"foo:bar").decode("ascii")
        assert store.headers["authorization"] == f"Basic {expected}"

    def test_init_from_env(self, mocker, mock_pool_manager):
        mocker.patch.dict(os.environ, WEBDAV_ENV, clear=True)
        store = WebDavStoreManager()
        assert store.url == "http://webdav:80"
        assert store.root == "servicex"
        expected = base64.b64encode(b"user:shhh").decode("ascii")
        assert store.headers["authorization"] == f"Basic {expected}"

    def test_init_without_auth(self, mocker, mock_pool_manager):
        mocker.patch.dict(os.environ, {"WEBDAV_URL": "http://webdav:80"}, clear=True)
        store = WebDavStoreManager()
        assert store.root == ""
        assert store.headers == {}

    def test_resource_url(self, mock_pool_manager):
        store = WebDavStoreManager("http://webdav", username=None, root="servicex")
        url = store._resource_url(store.root, "1234", "my results.parquet")
        assert url == "http://webdav/servicex/1234/my%20results.parquet"

    def test_upload_file(self, mock_pool_manager, result_file):
        http = mock_pool_manager.return_value
        http.request.side_effect = [response(201), response(201)]

        store = WebDavStoreManager(
            "http://webdav", username="foo", password="bar", root="servicex"
        )
        store.upload_file("1234", "result.parquet", str(result_file))

        mkcol_call, put_call = http.request.call_args_list
        assert mkcol_call.args == ("MKCOL", "http://webdav/servicex/1234")
        assert put_call.args == (
            "PUT",
            "http://webdav/servicex/1234/result.parquet",
        )
        assert put_call.kwargs["headers"]["Content-Length"] == str(len(b"some columns"))

        # The result is always cleaned off the sidecar's scratch volume
        assert not result_file.exists()

    def test_upload_file_existing_collection(self, mock_pool_manager, result_file):
        """MKCOL on a collection that is already there is not an error."""
        http = mock_pool_manager.return_value
        http.request.side_effect = [response(405), response(204)]

        store = WebDavStoreManager("http://webdav", username="foo", password="bar")
        store.upload_file("1234", "result.parquet", str(result_file))

        assert http.request.call_count == 2

    def test_upload_file_rejected(self, mock_pool_manager, result_file):
        http = mock_pool_manager.return_value
        http.request.side_effect = [response(201), response(403)]

        store = WebDavStoreManager("http://webdav", username="foo", password="bar")
        with pytest.raises(WebDavStoreError):
            store.upload_file("1234", "result.parquet", str(result_file))

        assert not result_file.exists()

    def test_upload_file_collection_rejected(self, mock_pool_manager, result_file):
        http = mock_pool_manager.return_value
        http.request.side_effect = [response(401)]

        store = WebDavStoreManager("http://webdav", username="foo", password="bar")
        with pytest.raises(WebDavStoreError):
            store.upload_file("1234", "result.parquet", str(result_file))

        # Never attempted the upload itself
        assert http.request.call_count == 1

    def test_upload_error_is_an_object_store_error(
        self, mock_pool_manager, result_file
    ):
        """
        The transformer handles all result store failures through
        ObjectStoreError, so WebDAV failures have to be caught by it too.
        """
        http = mock_pool_manager.return_value
        http.request.side_effect = [response(201), response(507)]

        store = WebDavStoreManager("http://webdav", username="foo", password="bar")
        with pytest.raises(ObjectStoreError):
            store.upload_file("1234", "result.parquet", str(result_file))
