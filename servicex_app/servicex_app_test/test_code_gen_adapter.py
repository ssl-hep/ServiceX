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
import pytest
from servicex_app.code_gen_adapter import CodeGenAdapter
from servicex_app.models import TransformRequest


class TestCodeGenAdapter:
    code_gen_service_urls = {
        'uproot': 'http://localhost:8000',
        'xAOD': 'http://localhost:8000',
        'python': 'http://localhost:8000'
    }

    def _generate_test_request(self):
        transform_request = TransformRequest()
        transform_request.request_id = "462-33"
        transform_request.selection = "test-string"
        return transform_request

    def test_init(self, mocker):
        mock_transformer_manager = mocker.MagicMock()
        service = CodeGenAdapter(self.code_gen_service_urls, mock_transformer_manager)
        assert service.code_gen_service_urls == self.code_gen_service_urls

    def test_generate_code_for_selection(self, mocker):

        mock_response = mocker.MagicMock()
        mock_response.status_code = 200

        mock_requests_post = mocker.patch('requests.post', return_value=mock_response)

        mock_parts = mocker.MagicMock()
        mock_transformer_image_part = mocker.MagicMock()
        mock_transformer_image_part.text = "my-transformer:test"

        mock_transformer_language_part = mocker.MagicMock()
        mock_transformer_language_part.text = "scala"

        mock_transformer_command_part = mocker.MagicMock()
        mock_transformer_command_part.text = "echo hello, world"

        mock_zip_part = mocker.MagicMock()

        mock_parts.parts = [mock_transformer_image_part,
                            mock_transformer_language_part,
                            mock_transformer_command_part,
                            mock_zip_part]
        mocker.patch('servicex_app.code_gen_adapter.decoder.MultipartDecoder.from_response',
                     return_value=mock_parts)

        mock_transformer_manager = mocker.MagicMock()
        mock_zip = mocker.patch("zipfile.ZipFile")
        mocker.patch("io.BytesIO")

        code_gen = CodeGenAdapter(self.code_gen_service_urls, mock_transformer_manager)
        (config_map, transformer_image, transformer_language, transformer_command) = \
            code_gen.generate_code_for_selection(self._generate_test_request(), "servicex", "uproot")

        assert transformer_image == "my-transformer:test"
        assert transformer_language == "scala"
        assert transformer_command == "echo hello, world"

        mock_requests_post.assert_called()
        mock_transformer_manager.create_configmap_from_zip.assert_called_with(mock_zip(),
                                                                              "462-33",
                                                                              "servicex")

    def test_generate_code_bad_response(self, mocker):
        mock_response = mocker.MagicMock()
        mock_response.status_code = 500
        mock_response.json = mocker.MagicMock(return_value={"Message": "Ooops"})
        mocker.patch('requests.post', return_value=mock_response)
        mock_transformer_manager = mocker.MagicMock()
        service = CodeGenAdapter(self.code_gen_service_urls, mock_transformer_manager)

        with pytest.raises(ValueError) as eek:
            service.generate_code_for_selection(self._generate_test_request(), "servicex", "uproot")
        assert str(eek.value) == 'Failed to generate translation code: Ooops'

    def test_wrong_user_input_codegen(self, mocker):
        mock_response = mocker.MagicMock()
        mock_response.status_code = 500
        mock_response.json = mocker.MagicMock(return_value={"Message": "Ooops"})
        mocker.patch('requests.post', return_value=mock_response)
        mock_transformer_manager = mocker.MagicMock()
        service = CodeGenAdapter(self.code_gen_service_urls, mock_transformer_manager)

        with pytest.raises(ValueError) as eek:
            service.generate_code_for_selection(self._generate_test_request(), "servicex", "foo")
        assert str(eek.value) == 'foo, code generator unavailable for use'
