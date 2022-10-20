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
import shutil

from func_adl.ast import ast_hash
from func_adl_uproot.translation import generate_python_source
from qastle import text_ast_to_python_ast

from servicex_codegen.code_generator import CodeGenerator, GeneratedFileResult, \
    GenerateCodeException


class AstUprootTranslator(CodeGenerator):
    # Generate the code. Ignoring caching for now
    def generate_code(self, query, cache_path: str):

        if len(query) == 0:
            raise GenerateCodeException("Requested codegen for an empty string.")

        body = text_ast_to_python_ast(query).body
        if len(body) != 1:
            raise GenerateCodeException(
                f'Requested codegen for "{query}" yielded no code statements (or too many).')  # noqa: E501
        a = body[0].value

        hash = ast_hash.calc_ast_hash(a)
        query_file_path = os.path.join(cache_path, hash)

        # Create the files to run in that location.
        if not os.path.exists(query_file_path):
            os.makedirs(query_file_path)

        src = generate_python_source(a)
        print(query_file_path)
        with open(os.path.join(query_file_path, 'generated_transformer.py'), 'w') as python_file:
            python_file.write(src)

        # Transfer the templated main python script
        template_path = os.environ.get('TEMPLATE_PATH',
                                       "/home/servicex/servicex/templates/transformer.py")
        shutil.copyfile(template_path, os.path.join(query_file_path, "transformer.py"))

        os.system("ls -lht " + query_file_path)

        return GeneratedFileResult(hash, query_file_path)
