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
import ast
import base64
import os
import shutil

from servicex_codegen.code_generator import (
    CodeGenerator,
    GeneratedFileResult,
    GenerateCodeException,
)

ALLOWED_COMPRESSION_ALGORITHMS = {"ZLIB", "LZMA", "LZ4", "ZSTD"}
ALLOWED_COMPRESSION_LEVELS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}


class PythonTranslator(CodeGenerator):

    # Generate the code. Ignoring caching for now
    def generate_code(self, query, cache_path: str):

        try:
            decoded = base64.b64decode(query)
        except ValueError as e:
            raise GenerateCodeException(f"Query is not valid base64: {e}")

        try:
            src = decoded.decode("utf-8")
        except UnicodeDecodeError as e:
            raise GenerateCodeException(f"Query is not valid UTF-8: {e}")

        try:
            ast.parse(src)
        except SyntaxError as e:
            raise GenerateCodeException(f"Query is not valid Python: {e}")

        compression_algorithm = os.environ.get("COMPRESSION_ALGORITHM", "ZSTD")
        try:
            compression_level = int(os.environ.get("COMPRESSION_LEVEL", 5))
        except ValueError:
            raise RuntimeError(
                f"Invalid compression level '{os.environ.get('COMPRESSION_LEVEL', 5)}'. "
            )

        if compression_algorithm not in ALLOWED_COMPRESSION_ALGORITHMS:
            raise RuntimeError(
                f"Invalid compression algorithm '{compression_algorithm}'. "
            )

        if compression_level not in ALLOWED_COMPRESSION_LEVELS:
            raise RuntimeError(f"Invalid compression level '{compression_level}'. ")

        src = f"""
import os
os.environ['COMPRESSION_ALGORITHM'] = '{compression_algorithm}'
os.environ['COMPRESSION_LEVEL'] = '{compression_level}'

{src}
"""
        hash = "no-hash"
        query_file_path = os.path.join(cache_path, hash)

        # Create the files to run in that location.
        if not os.path.exists(query_file_path):
            os.makedirs(query_file_path)

        with open(
            os.path.join(query_file_path, "generated_transformer.py"), "w"
        ) as python_file:
            python_file.write(src)

        # Transfer the templated main python script
        template_path = os.environ.get(
            "TEMPLATE_PATH",
            "/home/servicex/python_code_generator/templates/transform_single_file.py",
        )  # NOQA: 501
        shutil.copyfile(
            template_path, os.path.join(query_file_path, "transform_single_file.py")
        )

        capabilities_path = os.environ.get(
            "CAPABILITIES_PATH", "/home/servicex/transformer_capabilities.json"
        )
        shutil.copyfile(
            capabilities_path,
            os.path.join(query_file_path, "transformer_capabilities.json"),
        )

        os.system("ls -lht " + query_file_path)
        os.system(f"cat {query_file_path}/generated_transformer.py")
        return GeneratedFileResult(hash, query_file_path)
