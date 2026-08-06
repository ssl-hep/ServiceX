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
import logging
import os
import errno
import traceback

from tenacity import (
    RetryError,
    before_log,
    retry,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

import fsspec
from fsspec.exceptions import FSTimeoutError


class ObjectStoreError(Exception):
    pass


class ObjectStoreManager:

    def __init__(self, url=None, username=None, password=None, use_https=False):
        self.fs: fsspec.Filesystem
        protocol = os.environ.get("OBJECTSTORE_PROTOCOL", "s3")
        match protocol:
            case "s3":
                if "MINIO_ENCRYPT" in os.environ:
                    secure_connection = os.environ["MINIO_ENCRYPT"].lower() == "true"
                else:
                    secure_connection = use_https
                http_proto = "https" if secure_connection else "http"
                endpoint = f"{http_proto}://{url if url else os.environ['MINIO_URL']}"
                access_key = (username if username else os.environ["MINIO_ACCESS_KEY"],)
                secret_key = (password if password else os.environ["MINIO_SECRET_KEY"],)
                self.fs = fsspec.filesystem(
                    "s3",
                    endpoint_url=endpoint,
                    key=access_key,
                    secret=secret_key,
                )
            case "xrootd":
                storage_options = {"host": url if url else os.environ["MINIO_URL"]}
                xrd_user = username if username else os.environ.get("MINIO_ACCESS_KEY")
                xrd_pass = password if password else os.environ.get("MINIO_SECRET_KEY")
                if xrd_user is not None:
                    storage_options["user"] = xrd_user
                if xrd_pass is not None:
                    storage_options["pass"] = xrd_pass
                self.fs = fsspec.filesystem("root", **storage_options)
            case _:
                raise RuntimeError(f"Unknown protocol {protocol}")

        handler = logging.NullHandler()
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(handler)

    @retry(
        stop=stop_after_attempt(3),
        retry=retry_if_result(
            lambda e: (
                isinstance(e, FSTimeoutError)
                or (isinstance(e, OSError) and e.errno == errno.EBUSY)
            )
        ),
        wait=wait_exponential(multiplier=3, exp_base=4) + wait_random(min=1, max=3),
        before=before_log(logging.getLogger(__name__), logging.INFO),
    )
    def _upload_file_with_retry(self, bucket, object_name, path):
        """
        Upload a file to the object store with retry logic for certain S3 errors.
        To take advantage of tenacity's retry logic based on specific errors, this
        function needs to return the exception rather than raise it.
        """
        try:
            result = self.fs.put_file(lpath=path, rpath=f"{bucket}/{object_name}")
        except Exception as e:
            # retry_if_result needs the exception to be returned and not raised
            return e
        return result

    def upload_file(self, bucket, object_name, path):
        try:
            result = self._upload_file_with_retry(bucket, object_name, path)

            # The retry logic will return the exception rather than raise it
            if isinstance(result, Exception):
                raise result

            self.logger.info(
                "OSM > created object.",
                extra={
                    "request_id": bucket,
                    "object_name": result.object_name,
                },
            )

        except (RetryError, OSError) as e:
            # If a non-retryable OSError is raised it will come here. If we
            # ran out of retries it will also come here, but the exception will
            # wrapped by tenacity
            self.logger.error("OSError", exc_info=True)
            traceback.print_exc()
            raise ObjectStoreError(f"Error uploading file to storage: {path}") from e

        except Exception as e:
            self.logger.error("Upload error", exc_info=True)
            traceback.print_exc()
            raise ObjectStoreError(f"Error uploading file to storage: {path}") from e

        finally:
            # Delete the file regardless of success or failure
            try:
                os.remove(path)
            except FileNotFoundError:
                pass  # Should never happen, but is not fatal if it occurs
