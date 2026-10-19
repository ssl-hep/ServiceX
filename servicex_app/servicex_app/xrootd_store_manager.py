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

import fsspec
from tenacity import retry, stop_after_attempt, wait_random_exponential


class XRootDStoreManager:
    """
    Manages transform results held on an xRootD storage element rather than in
    an S3 object store. All outputs live under a single top level URL provided
    by the deployment, with one subdirectory per transform named after the
    request id. That subdirectory plays the role of the S3 bucket, so this class
    offers the same interface as ObjectStoreManager.

    Access to the storage element comes from the X509 proxy mounted into the
    pod, so there are no credentials to configure.
    """

    # Where the pod gets the X509 proxy secret mounted
    MOUNTED_PROXY = "/etc/grid-security-ro/x509up"

    def __init__(self, url):
        self._stage_proxy()
        self.url = url.rstrip("/")
        self.filesystem, self.root_path = fsspec.core.url_to_fs(self.url)
        self.root_path = self.root_path.rstrip("/")

    @staticmethod
    def _stage_proxy():
        """
        The proxy secret is mounted read-only and group readable, which the
        XRootD client will not use, so copy it somewhere writable with
        owner-only permissions.
        """
        proxy_path = os.environ.get("X509_USER_PROXY")
        if not proxy_path or not os.path.exists(XRootDStoreManager.MOUNTED_PROXY):
            return

        try:
            os.makedirs(os.path.dirname(proxy_path), exist_ok=True)
            shutil.copyfile(XRootDStoreManager.MOUNTED_PROXY, proxy_path)
            os.chmod(proxy_path, 0o600)
        except OSError:
            # Not necessarily fatal - the storage element may not need the proxy
            logging.getLogger(__name__).warning(
                "Could not stage X509 proxy", exc_info=True
            )

    def _bucket_path(self, bucket_name):
        return "/".join([self.root_path, bucket_name])

    @retry(
        stop=stop_after_attempt(3), wait=wait_random_exponential(max=60), reraise=True
    )
    def create_bucket(self, bucket_name):
        # Re-stage on every write: the proxy secret is refreshed periodically
        self._stage_proxy()
        self.filesystem.makedirs(self._bucket_path(bucket_name), exist_ok=True)

    def list_buckets(self):
        return self.filesystem.ls(self.root_path, detail=False)

    def delete_bucket_and_contents(self, bucket_name):
        self._stage_proxy()
        bucket_path = self._bucket_path(bucket_name)
        if not self.filesystem.exists(bucket_path):
            print(f"Directory '{bucket_path}' does not exist. Nothing to delete.")
            return

        self.filesystem.rm(bucket_path, recursive=True)
        print(f"Directory '{bucket_path}' deleted successfully.")
