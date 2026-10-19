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

from servicex_app.xrootd_store_manager import XRootDStoreManager

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
    return mocker.patch.object(XRootDStoreManager, "_stage_proxy")


class TestXRootDStoreManager:
    def test_init(self, mock_filesystem, no_proxy):
        store = XRootDStoreManager(STORE_URL + "/")
        assert store.url == STORE_URL
        assert store.root_path == "/servicex/outputs"

    def test_create_bucket(self, mock_filesystem, no_proxy):
        store = XRootDStoreManager(STORE_URL)
        store.create_bucket("123-456")
        mock_filesystem.makedirs.assert_called_with(
            "/servicex/outputs/123-456", exist_ok=True
        )

    def test_list_buckets(self, mock_filesystem, no_proxy):
        mock_filesystem.ls.return_value = ["/servicex/outputs/a"]
        store = XRootDStoreManager(STORE_URL)
        assert store.list_buckets() == ["/servicex/outputs/a"]
        mock_filesystem.ls.assert_called_with("/servicex/outputs", detail=False)

    def test_delete_bucket_and_contents(self, mock_filesystem, no_proxy):
        mock_filesystem.exists.return_value = True
        store = XRootDStoreManager(STORE_URL)
        store.delete_bucket_and_contents("123-456")
        mock_filesystem.rm.assert_called_with(
            "/servicex/outputs/123-456", recursive=True
        )

    def test_delete_bucket_and_contents_no_bucket(self, mock_filesystem, no_proxy):
        mock_filesystem.exists.return_value = False
        store = XRootDStoreManager(STORE_URL)
        store.delete_bucket_and_contents("123-456")
        mock_filesystem.rm.assert_not_called()

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
