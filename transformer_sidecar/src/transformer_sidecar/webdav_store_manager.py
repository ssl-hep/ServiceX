# Copyright (c) 2025, IRIS-HEP
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
import traceback
from urllib.parse import quote

import urllib3
from tenacity import (
    RetryError,
    before_log,
    retry,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

from transformer_sidecar.object_store_manager import ObjectStoreError


class WebDavStoreError(ObjectStoreError):
    """
    Raised when a result can't be written to the WebDAV server. Subclasses
    ObjectStoreError so that the transformer's upload error handling is the
    same no matter which result store is in use.
    """


# Transient server side conditions. Anything else (401, 403, 507, ...) is a
# hard failure - retrying won't help.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# MKCOL returns 405 when the collection is already there, which is the common
# case since every file of a request goes into the same collection.
MKCOL_OK_STATUS = frozenset({201, 405})

PUT_OK_STATUS = frozenset({200, 201, 204})


def _is_retryable(result):
    """
    tenacity predicate. The retried methods return rather than raise their
    errors so that the connection level failures and the retryable HTTP
    statuses can be treated the same way.
    """
    if isinstance(result, Exception):
        return True
    return result.status in RETRYABLE_STATUS


class WebDavStoreManager:
    """
    Writes transform results to a WebDAV server. Presents the same
    upload_file(bucket, object_name, path) interface as ObjectStoreManager -
    each request id becomes a collection under the configured root and each
    result file becomes a resource within it.
    """

    def __init__(self, url=None, username=None, password=None, root=None):
        handler = logging.NullHandler()
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(handler)

        self.url = (url if url else os.environ["WEBDAV_URL"]).rstrip("/")
        root = root if root is not None else os.environ.get("WEBDAV_ROOT", "")
        self.root = root.strip("/")

        username = username if username else os.environ.get("WEBDAV_USERNAME")
        password = password if password else os.environ.get("WEBDAV_PASSWORD")
        self.headers = (
            urllib3.make_headers(basic_auth=f"{username}:{password or ''}")
            if username
            else {}
        )

        # urllib3 does its own retries by default. Turn them off so that the
        # tenacity policy below is the only one in play.
        self.http = urllib3.PoolManager(retries=False)

    def _resource_url(self, *parts):
        """
        Build the URL of a collection or resource below the configured root.
        Path separators in the parts are preserved, everything else is escaped.
        """
        path = "/".join(quote(p.strip("/"), safe="/") for p in parts if p)
        return f"{self.url}/{path}"

    @retry(
        stop=stop_after_attempt(3),
        retry=retry_if_result(_is_retryable),
        wait=wait_exponential(multiplier=3, exp_base=4) + wait_random(min=1, max=3),
        before=before_log(logging.getLogger(__name__), logging.INFO),
    )
    def _mkcol_with_retry(self, url):
        try:
            return self.http.request("MKCOL", url, headers=self.headers)
        except urllib3.exceptions.HTTPError as e:
            # retry_if_result needs the exception to be returned and not raised
            return e

    @retry(
        stop=stop_after_attempt(3),
        retry=retry_if_result(_is_retryable),
        wait=wait_exponential(multiplier=3, exp_base=4) + wait_random(min=1, max=3),
        before=before_log(logging.getLogger(__name__), logging.INFO),
    )
    def _put_file_with_retry(self, url, path):
        # Opened per attempt so that a retry streams the file from the start.
        try:
            with open(path, "rb") as source:
                headers = dict(self.headers)
                headers["Content-Length"] = str(os.path.getsize(path))
                return self.http.request("PUT", url, headers=headers, body=source)
        except urllib3.exceptions.HTTPError as e:
            # retry_if_result needs the exception to be returned and not raised
            return e

    @staticmethod
    def _check(result, ok_status, message):
        """
        Turn whatever the retried request came back with into either a
        successful response or a WebDavStoreError.
        """
        if isinstance(result, Exception):
            raise WebDavStoreError(message) from result
        if result.status not in ok_status:
            raise WebDavStoreError(f"{message}: HTTP {result.status}")
        return result

    def create_collection(self, bucket):
        """
        Create the collection a request's results live in. Safe to call for
        every file - an existing collection is not an error.
        """
        url = self._resource_url(self.root, bucket)
        self._check(
            self._mkcol_with_retry(url),
            MKCOL_OK_STATUS,
            f"Error creating WebDAV collection: {url}",
        )

    def upload_file(self, bucket, object_name, path):
        try:
            self.create_collection(bucket)

            url = self._resource_url(self.root, bucket, object_name)
            self._check(
                self._put_file_with_retry(url, path),
                PUT_OK_STATUS,
                f"Error uploading file to WebDAV server: {path}",
            )

            self.logger.info(
                "WebDAV > created object.",
                extra={"request_id": bucket, "object_name": object_name},
            )

        except RetryError as e:
            # We ran out of retries, so the last attempt is wrapped by tenacity
            self.logger.error("WebDAV error", exc_info=True)
            traceback.print_exc()
            raise WebDavStoreError(
                f"Error uploading file to WebDAV server: {path}"
            ) from e

        except WebDavStoreError:
            self.logger.error("WebDAV error", exc_info=True)
            traceback.print_exc()
            raise

        finally:
            # Delete the file regardless of success or failure
            try:
                os.remove(path)
            except FileNotFoundError:
                pass  # Should never happen, but is not fatal if it occurs
