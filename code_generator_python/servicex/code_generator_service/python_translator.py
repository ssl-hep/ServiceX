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
import zipfile
from collections import namedtuple
from tempfile import TemporaryDirectory
from typing import Optional, Union
from pathlib import Path
import base64

GeneratedFileResult = namedtuple('GeneratedFileResult', 'hash output_dir')


class GenerateCodeException(BaseException):
    """Custom exception for top level code generation exceptions"""

    def __init__(self, message: str):
        BaseException.__init__(self, message)


class PythonTranslator:
    def __init__(self):
        pass
    
    def zipdir(self, path: str, zip_handle: zipfile.ZipFile) -> None:
        """Given a `path` to a directory, zip up its contents into a zip file.
        Arguments:
            path        Path to a local directory. The contents will be put into the zip file
            zip_handle  The zip file handle to write into.
        """
        for root, _, files in os.walk(path):
            for file in files:
                zip_handle.write(os.path.join(root, file), file)

    # Generate the code. Ignoring caching for now
    def get_generated_python(self, a, cache_path: str):
        import hashlib
        hash = hashlib.md5(a).hexdigest()
        query_file_path = os.path.join(cache_path, hash)

        # Create the files to run in that location.
        if not os.path.exists(query_file_path):
            os.makedirs(query_file_path)

        message_bytes = base64.b64decode(a)
        src = message_bytes.decode('ascii')

        with open(os.path.join(query_file_path, 'generated_transformer.py'), 'w') as python_file:
            python_file.write(src)

        os.system("ls -lht " + query_file_path)
        return GeneratedFileResult(hash, query_file_path)
    
    def translate_text_python_to_zip(self, code: str) -> bytes:
        """Translate a text python into a zip file as a memory stream

        Arguments:
            code            Text `python` function

        Returns
            bytes       Data that if written as a binary output would be a zip file.
        """

        if len(code) == 0:
            raise GenerateCodeException("Requested codegen for an empty string.")

        # Generate the python code
        with TemporaryDirectory() as tempdir:
            # Zip up everything in the directory - we are going to ship it as back as part
            # of the message.
            r = self.get_generated_python(code, tempdir)
            z_filename = os.path.join(str(tempdir), 'joined.zip')
            zip_h = zipfile.ZipFile(z_filename, 'w', zipfile.ZIP_DEFLATED)
            self.zipdir(r.output_dir, zip_h)
            zip_h.close()

            with open(z_filename, 'rb') as b_in:
                return b_in.read()
