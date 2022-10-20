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
from pathlib import Path
from typing import Optional, Union

from func_adl_xAOD.atlas.xaod.executor import atlas_xaod_executor
from func_adl_xAOD.cms.aod.executor import cms_aod_executor
from func_adl_xAOD.common.executor import executor
from qastle import text_ast_to_python_ast

from servicex_codegen.code_generator import CodeGenerator, GeneratedFileResult, \
    GenerateCodeException


class AstAODTranslator(CodeGenerator):
    def __init__(self, exe: Optional[Union[executor, str]] = None):
        '''
        Create the ast translator objects

        Arguments

            executor    The object that will do the translation if an executor is specified or
                        if it's a string then appropriate executor is chosen
        '''
        if isinstance(exe, str) or not exe:
            if exe == 'CMS AOD':
                self._exe = cms_aod_executor()
            elif exe == 'ATLAS xAOD':
                self._exe = atlas_xaod_executor()
            else:
                raise ValueError(f'The executor name, {exe}, must be "CMS AOD" or "ATLAS xAOD" only.')  # noqa: E501
        else:
            self._exe = exe

    @property
    def executor(self):
        return self._exe

    def generate_code(self, query, cache_path: str):
        path = Path(cache_path)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

        if len(query) == 0:
            raise GenerateCodeException("Requested codegen for an empty string.")

        body = text_ast_to_python_ast(query).body

        if len(body) != 1:
            raise GenerateCodeException(
                f'Requested codegen for "{query}" yielded no code statements (or too many).')  # noqa: E501
        a = body[0].value

        self._exe.write_cpp_files(
            self._exe.apply_ast_transformations(a), path)

        # Transfer the templated pilot bash script
        template_path = os.environ.get('TEMPLATE_PATH',
                                       "/home/servicex/servicex/templates/transform_single_file.sh") # NOQA: 501
        shutil.copyfile(template_path, os.path.join(path, "transform_single_file.sh"))

        os.system("ls -lht " + cache_path)

        return GeneratedFileResult(hash, cache_path)
