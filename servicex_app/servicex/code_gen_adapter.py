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
import requests
from requests_toolbelt.multipart import decoder
from servicex.models import TransformRequest


class CodeGenAdapter:
    def __init__(self, code_gen_url, transformer_manager):
        self.code_gen_url = code_gen_url
        self.transformer_manager = transformer_manager

    def generate_code_for_selection(
            self, request_record: TransformRequest, namespace: str, transformer_image: str = None):
        """
        Generates the C++ code for a request's selection string.
        Places the results in a ConfigMap resource in the
        Starts a transformation request, deploys transformers, and updates record.
        :param request_record: A TransformationRequest.
        :param namespace: Namespace in which to place resulting ConfigMap.
        :param transformer_image: Set optional transformer image name for the request
        """
        from io import BytesIO
        from zipfile import ZipFile

        postObj = {
            "code": request_record.selection,
        }

        result = requests.post(self.code_gen_url + "/servicex/generated-code",
                               json=postObj)

        if result.status_code != 200:
            msg = result.json()['Message']
            raise ValueError(f'Failed to generate translation code: {msg}')

        # Multipart Mime Encoder from requests_toolbelt appends a delimited between all the fields mentioned in the data payload
        # Here we are using two constants START_INDEX=2 and END_INDEX=34 which will extract the delimiter from the string
        # The delimiter is used by the decoder to extract the data out the individual fields from the multipart data

        START_INDEX = 2
        END_INDEX = 34
        boundary = result.data[START_INDEX:END_INDEX].decode('utf-8')
        content_type = f"multipart/form-data; boundary={boundary}"
        decoder_parts = decoder.MultipartDecoder(result.data, content_type)

        assert self.transformer_manager, "Code Generator won't work without a Transformer Manager"

        if len(decoder_parts.parts) > 1:
            transformer_image = str(decoder_parts.parts[0].content, 'utf-8')
            zipfile = decoder_parts.parts[1].content

            zipfile = ZipFile(BytesIO(zipfile))

            return (self.transformer_manager.create_configmap_from_zip(zipfile,
                                                                       request_record.request_id,
                                                                       namespace), transformer_image)
        else:

            zipfile = ZipFile(BytesIO(""))

            return (self.transformer_manager.create_configmap_from_zip(zipfile,
                                                                       request_record.request_id,
                                                                       namespace), transformer_image)
