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
from _ast import AST
from types import SimpleNamespace
import pytest


class TestASTTranslator:
    def test_translate_uproot(self, mocker):
        mock_uproot_generator = \
            mocker.patch("func_adl_uproot.translation.generate_python_source",
                         return_value="import uproot")
        mock_ast = SimpleNamespace()
        mock_ast.value = AST()
        mock_result = SimpleNamespace()
        mock_result.body = [mock_ast]
        mock_text_to_python_ast = mocker.patch("qastle.text_ast_to_python_ast",
                                               return_value=mock_result)
        from servicex.code_generator_service import AstTranslator

        ast_translator = AstTranslator('uproot')
        ast_translator.translate_text_ast_to_zip("(foo (bar))")

        mock_text_to_python_ast.assert_called_with("(foo (bar))")
        mock_uproot_generator.assert_called_with(mock_ast.value)

    def test_bad_constructor_arg(self):
        with pytest.raises(AssertionError):
            from servicex.code_generator_service import AstTranslator
            AstTranslator('blah')
