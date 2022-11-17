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
import os

from transformer_sidecar.object_store_manager import ObjectStoreManager


class TestObjectStoreManager:
    def test_init(self, mocker):
        mock_minio = mocker.patch('minio.Minio')
        ObjectStoreManager('localhost:9999', 'foo', 'bar')
        called_config = mock_minio.call_args[1]
        assert called_config['endpoint'] == 'localhost:9999'
        assert called_config['access_key'] == 'foo'
        assert called_config['secret_key'] == 'bar'
        assert not called_config['secure']

        ObjectStoreManager('localhost:9999', 'foo', 'bar', True)
        called_config = mock_minio.call_args[1]
        assert called_config['endpoint'] == 'localhost:9999'
        assert called_config['access_key'] == 'foo'
        assert called_config['secret_key'] == 'bar'
        assert called_config['secure']

    def test_init_from_env(self, mocker):
        os.environ['MINIO_URL'] = 'localhost:9999'
        os.environ['MINIO_ACCESS_KEY'] = 'test'
        os.environ['MINIO_SECRET_KEY'] = 'shhh'
        mock_minio = mocker.patch('minio.Minio')

        ObjectStoreManager()
        called_config = mock_minio.call_args[1]
        assert called_config['endpoint'] == 'localhost:9999'
        assert called_config['access_key'] == 'test'
        assert called_config['secret_key'] == 'shhh'
        assert not called_config['secure']

        os.environ['MINIO_ENCRYPT'] = "True"
        ObjectStoreManager()
        called_config = mock_minio.call_args[1]
        assert called_config['endpoint'] == 'localhost:9999'
        assert called_config['access_key'] == 'test'
        assert called_config['secret_key'] == 'shhh'
        assert called_config['secure']

    def test_upload_file(self, mocker):
        import minio
        mock_minio = mocker.MagicMock(minio.api.Minio)
        mock_minio.fput_object = mocker.Mock()
        mocker.patch('minio.Minio', return_value=mock_minio)
        result = ObjectStoreManager('localhost:9999', 'foo', 'bar')
        result.upload_file("my-bucket", "foo.txt", "/tmp/foo.txt")
        mock_minio.fput_object.assert_called()
