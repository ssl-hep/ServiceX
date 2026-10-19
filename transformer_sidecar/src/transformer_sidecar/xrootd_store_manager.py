# Copyright (c) 2026, IRIS-HEP
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
import shutil
import traceback

import fsspec
from tenacity import (
    before_log,
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

from transformer_sidecar.object_store_manager import ObjectStoreError


class XRootDStoreManager:
    """
    Writes transform results to an xRootD storage element instead of an S3
    object store. The deployment provides a top level URL under which all
    outputs live; each transform gets a subdirectory named after its request id,
    so this class presents the same bucket/object interface as
    ObjectStoreManager.

    Authentication is handled by the X509 proxy that is already mounted into the
    transformer pod, so there are no credentials to pass along here.
    """

    # Where the transformer pod gets the X509 proxy secret mounted
    MOUNTED_PROXY = "/etc/grid-security-ro/x509up"

    def __init__(self, url=None):
        handler = logging.NullHandler()
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(handler)

        self._stage_proxy()

        self.url = (url if url else os.environ["XROOTD_STORE_URL"]).rstrip("/")
        self.filesystem, self.root_path = fsspec.core.url_to_fs(self.url)

    def _stage_proxy(self):
        """
        The proxy secret is mounted read-only and group readable, which the
        XRootD client will not use, so copy it somewhere writable with
        owner-only permissions. This is the same thing proxy-exporter.sh does
        for the science container. If there is no mounted proxy then we leave
        whatever is already in place alone.
        """
        proxy_path = os.environ.get("X509_USER_PROXY")
        if not proxy_path or not os.path.exists(self.MOUNTED_PROXY):
            return

        try:
            os.makedirs(os.path.dirname(proxy_path), exist_ok=True)
            shutil.copyfile(self.MOUNTED_PROXY, proxy_path)
            os.chmod(proxy_path, 0o600)
        except OSError:
            # Not necessarily fatal - the storage element may not need the proxy
            self.logger.warning("Could not stage X509 proxy", exc_info=True)

    def _object_path(self, bucket, object_name):
        """
        Path of a transform output within the storage element. The bucket is the
        request id, which names the transform's subdirectory of the root path.
        """
        return "/".join([self.root_path.rstrip("/"), bucket, object_name])

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10) + wait_random(min=1, max=3),
        before=before_log(logging.getLogger(__name__), logging.INFO),
        reraise=True,
    )
    def _upload_file_with_retry(self, bucket, object_name, path):
        """
        Copy a file to the storage element, retrying a few times since xRootD
        writes can fail transiently while a server is busy or restarting.
        """
        destination = self._object_path(bucket, object_name)
        self.filesystem.makedirs(os.path.dirname(destination), exist_ok=True)
        self.filesystem.put_file(path, destination)
        return destination

    def upload_file(self, bucket, object_name, path):
        try:
            destination = self._upload_file_with_retry(bucket, object_name, path)

            self.logger.info(
                "XRootD > created object.",
                extra={"request_id": bucket, "object_name": object_name},
            )
            return destination

        except Exception as e:
            self.logger.error("XRootD error", exc_info=True)
            traceback.print_exc()
            raise ObjectStoreError(
                f"Error uploading file to xrootd store: {path}"
            ) from e

        finally:
            # Delete the file regardless of success or failure
            try:
                os.remove(path)
            except FileNotFoundError:
                pass  # Should never happen, but is not fatal if it occurs
