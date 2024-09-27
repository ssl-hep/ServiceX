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
from tenacity import Retrying, stop_after_attempt, wait_exponential_jitter
from requests_toolbelt.multipart import decoder
from servicex_app.models import TransformRequest


class CodeGenAdapter:
    def __init__(self, code_gen_service_urls, transformer_manager):
        self.code_gen_service_urls = code_gen_service_urls
        self.transformer_manager = transformer_manager

    def generate_code_for_selection(
            self, request_record: TransformRequest,
            namespace: str,
            user_codegen_name: str) -> tuple[str, str, str, str]:
        """
        Generates the C++ code for a request's selection string.
        Places the results in a ConfigMap resource in the
        Starts a transformation request, deploys transformers, and updates record.
        :param request_record: A TransformationRequest.
        :param namespace: Namespace in which to place resulting ConfigMap.
        :param user_codegen_name: Name provided by user for selecting the codegen URL from config dictionary
        :returns a tuple of (config map name, default transformer image)
        """
        from io import BytesIO
        from zipfile import ZipFile

        assert self.transformer_manager, "Code Generator won't work without a Transformer Manager"

        # Finding Codegen URL from the config dictionary and user provided input
        post_url = self.code_gen_service_urls.get(user_codegen_name, None)

        if not post_url:
            raise ValueError(f'{user_codegen_name}, code generator unavailable for use')

        postObj = {
            "code": request_record.selection,
        }

        for attempt in Retrying(stop=stop_after_attempt(3),
                                wait=wait_exponential_jitter(initial=0.1, max=30),
                                reraise=True):
            with attempt:
                result = requests.post(post_url + "/servicex/generated-code", json=postObj,
                                       timeout=(0.5, None))

        if result.status_code != 200:
            msg = result.json()['Message']
            raise ValueError(f'Failed to generate translation code: {msg}')

        decoder_parts = decoder.MultipartDecoder.from_response(result)

        transformer_image = (decoder_parts.parts[0].text).strip()
        transformer_language = (decoder_parts.parts[1].text).strip()
        transformer_command = (decoder_parts.parts[2].text).strip()
        zipfile = decoder_parts.parts[3].content

        zipfile = ZipFile(BytesIO(zipfile))

        return (self.transformer_manager.create_configmap_from_zip(zipfile,
                                                                   request_record.request_id,
                                                                   namespace),
                transformer_image,
                transformer_language,
                transformer_command)
