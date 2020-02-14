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
from servicex.code_generator_service import create_app
import io
import zipfile

from servicex.code_generator_service.ast_translator import GenerateCodeException


def get_zipfile_data(zip_data: bytes):
    with zipfile.ZipFile(io.BytesIO(zip_data)) as thezip:
        for zipinfo in thezip.infolist():
            with thezip.open(zipinfo) as thefile:
                yield zipinfo.filename, thefile


def check_zip_file(zip_data: bytes):
    names = []
    for name, data in get_zipfile_data(zip_data):
        names.append(name)
        print(name)
    assert len(names) == 6


class TestGenerateCode:
    def test_post_good_query(self, mocker):
        """Produce code for a simple good query"""

        mock_ast_translator = mocker.Mock()
        mock_ast_translator.translate_text_ast_to_zip = mocker.Mock(return_value="hi")

        config = {
            'TARGET_BACKEND': 'uproot'
        }
        app = create_app(config, provided_translator=mock_ast_translator)
        client = app.test_client()
        select_stmt = "(call ResultTTree (call Select (call SelectMany (call EventDataset (list 'localds://did_01')"  # noqa: E501

        response = client.post("/servicex/generated-code", data=select_stmt)
        assert response.status_code == 200
        mock_ast_translator.translate_text_ast_to_zip.assert_called_with(select_stmt)

    def test_post_codegen_error_query(self, mocker):
        """Post a query with a code-gen level error"""
        mock_ast_translator = mocker.Mock()
        mock_ast_translator.translate_text_ast_to_zip = \
            mocker.Mock(side_effect=GenerateCodeException)

        config = {
            'TARGET_BACKEND': 'uproot'
        }
        app = create_app(config, provided_translator=mock_ast_translator)
        client = app.test_client()
        select_stmt = "(call ResultTTree (call Select (call SelectMany (call EventDataset (list 'localds://did_01')"  # noqa: E501

        response = client.post("/servicex/generated-code", data=select_stmt)

        assert response.status_code == 500
        assert 'Message' in response.json
