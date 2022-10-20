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
import logging
from minio.error import MinioException, S3Error


class ObjectStoreManager:

    def __init__(self, url=None, username=None, password=None, use_https=False):

        from minio import Minio
        handler = logging.NullHandler()
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(handler)

        if 'MINIO_ENCRYPT' in os.environ:
            secure_connection = os.environ['MINIO_ENCRYPT'].lower() == "true"
        else:
            secure_connection = use_https
        self.minio_client = Minio(endpoint=url if url else os.environ[
            'MINIO_URL'],
            access_key=username if username else os.environ[
            'MINIO_ACCESS_KEY'],
            secret_key=password if password else os.environ[
            'MINIO_SECRET_KEY'],
            secure=secure_connection)

    def upload_file(self, bucket, object_name, path):
        try:
            result = self.minio_client.fput_object(bucket_name=bucket,
                                                   object_name=object_name,
                                                   file_path=path)
            self.logger.debug(
                "created object", result.object_name)
        except MinioException:
            self.logger.error("Minio error", exc_info=True)
        except S3Error:
            self.logger.error("S3Error", exc_info=True)
