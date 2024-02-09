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
import tempfile
from collections import namedtuple

import pytest
from uproot_code_generator.ast_translator import GenerateCodeException, \
    AstUprootTranslator


class TestGenerateCode:
    def test_post_good_query(self, mocker):
        mock_transform = namedtuple('GeneratedFileResult', 'body')(body=[
            namedtuple('GeneratedFileBody', 'value')(value="hi")
        ])
        mock_translator = mocker.patch(
            "uproot_code_generator.ast_translator.text_ast_to_python_ast",
            return_value=mock_transform)
        mock_hash = mocker.patch(
            "uproot_code_generator.ast_translator.ast_hash.calc_ast_hash",
            return_value="123-456")
        gen_python_source = mocker.patch(
            "uproot_code_generator.ast_translator.generate_python_source",
            return_value="import foo")

        with tempfile.TemporaryDirectory() as tmpdirname:
            os.environ['TEMPLATE_PATH'] = "uproot_code_generator/templates/transform_single_file.py" # NOQA E501
            os.environ['CAPABILITIES_PATH'] = "transformer_capabilities.json"
            query = "(Select (call EventDataset) (lambda (list event) (dict (list 'pt' 'eta') (list (attr event 'Muon_pt') (attr event 'Muon_eta')))))" # NOQA E501

            translator = AstUprootTranslator()
            generated = translator.generate_code(
                query,
                cache_path=tmpdirname)

            assert generated.output_dir.startswith(tmpdirname)
            mock_translator.assert_called_with(query)
            mock_hash.assert_called_with("hi")
            gen_python_source.assert_called_with("hi")

    def test_post_codegen_error_query(self):
        """Post a query with a code-gen level error"""
        with tempfile.TemporaryDirectory() as tmpdirname:
            translator = AstUprootTranslator()
            with pytest.raises(GenerateCodeException):
                translator.generate_code("", cache_path=tmpdirname)
