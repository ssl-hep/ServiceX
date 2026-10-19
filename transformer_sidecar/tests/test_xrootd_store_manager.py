# Copyright (c) 2026, IRIS-HEP
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
import os
import stat

import pytest

from transformer_sidecar.object_store_manager import ObjectStoreError
from transformer_sidecar.xrootd_store_manager import XRootDStoreManager

STORE_URL = "root://my.storage.org:1094//servicex/outputs"


@pytest.fixture
def mock_filesystem(mocker):
    """Stand in for the fsspec filesystem behind the store URL"""
    filesystem = mocker.MagicMock()
    mocker.patch(
        "fsspec.core.url_to_fs", return_value=(filesystem, "/servicex/outputs")
    )
    return filesystem


@pytest.fixture
def no_proxy(mocker):
    """Keep the proxy staging out of the way of the upload tests"""
    return mocker.patch.object(XRootDStoreManager, "_stage_proxy")


@pytest.fixture
def source_file(tmp_path):
    path = tmp_path / "results.parquet"
    path.write_text("some results")
    return path


class TestXRootDStoreManager:
    def test_init(self, mocker, mock_filesystem, no_proxy):
        store = XRootDStoreManager(STORE_URL + "/")
        assert store.url == STORE_URL
        assert store.root_path == "/servicex/outputs"

    def test_init_from_env(self, mocker, mock_filesystem, no_proxy):
        mocker.patch.dict(os.environ, {"XROOTD_STORE_URL": STORE_URL})
        store = XRootDStoreManager()
        assert store.url == STORE_URL

    def test_upload_file(self, mock_filesystem, no_proxy, source_file):
        store = XRootDStoreManager(STORE_URL)
        store.upload_file("123-456", "results.parquet", source_file.as_posix())

        mock_filesystem.makedirs.assert_called_with(
            "/servicex/outputs/123-456", exist_ok=True
        )
        mock_filesystem.put_file.assert_called_with(
            source_file.as_posix(), "/servicex/outputs/123-456/results.parquet"
        )

        # The local copy is always cleaned up
        assert not source_file.exists()

    def test_upload_file_retries(self, mocker, mock_filesystem, no_proxy, source_file):
        mocker.patch("tenacity.nap.time.sleep")
        mock_filesystem.put_file.side_effect = [OSError("server busy"), None]

        store = XRootDStoreManager(STORE_URL)
        store.upload_file("123-456", "results.parquet", source_file.as_posix())

        assert mock_filesystem.put_file.call_count == 2
        assert not source_file.exists()

    def test_upload_file_error(self, mocker, mock_filesystem, no_proxy, source_file):
        mocker.patch("tenacity.nap.time.sleep")
        mock_filesystem.put_file.side_effect = OSError("permission denied")

        store = XRootDStoreManager(STORE_URL)
        with pytest.raises(ObjectStoreError):
            store.upload_file("123-456", "results.parquet", source_file.as_posix())

        assert mock_filesystem.put_file.call_count == 3

        # Even a failed upload shouldn't leave the file filling up the pod
        assert not source_file.exists()

    def test_upload_file_missing_source(self, mock_filesystem, no_proxy, tmp_path):
        """Deleting a file that has already gone isn't fatal"""
        mock_filesystem.put_file.side_effect = None
        store = XRootDStoreManager(STORE_URL)
        store.upload_file(
            "123-456", "results.parquet", (tmp_path / "not-here").as_posix()
        )

    def test_stage_proxy(self, mocker, mock_filesystem, tmp_path):
        mounted = tmp_path / "mounted" / "x509up"
        mounted.parent.mkdir()
        mounted.write_text("proxy contents")
        staged = tmp_path / "staged" / "x509up"

        mocker.patch.object(XRootDStoreManager, "MOUNTED_PROXY", mounted.as_posix())
        mocker.patch.dict(os.environ, {"X509_USER_PROXY": staged.as_posix()})

        XRootDStoreManager(STORE_URL)

        assert staged.read_text() == "proxy contents"
        assert stat.S_IMODE(staged.stat().st_mode) == 0o600

    def test_stage_proxy_without_mount(self, mocker, mock_filesystem, tmp_path):
        """Nothing to stage when the pod has no proxy secret mounted"""
        staged = tmp_path / "staged" / "x509up"
        mocker.patch.object(
            XRootDStoreManager, "MOUNTED_PROXY", (tmp_path / "absent").as_posix()
        )
        mocker.patch.dict(os.environ, {"X509_USER_PROXY": staged.as_posix()})

        XRootDStoreManager(STORE_URL)

        assert not staged.exists()
