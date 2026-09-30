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
from urllib.parse import quote

import requests
from tenacity import retry, stop_after_attempt, wait_random_exponential

# The transformers upload the results, so all the app has to do is clean them
# up again when a transform is deleted.
DELETE_TIMEOUT = 60


class WebDavManager:
    """
    The app's view of the WebDAV server results are written to. Each request
    id is a collection below the server's configured root.
    """

    def __init__(self, url, root="", username=None, password=None):
        self.url = url.rstrip("/")
        self.root = (root or "").strip("/")
        self.auth = (username, password or "") if username else None

    def collection_url(self, request_id):
        path = "/".join(
            quote(p.strip("/"), safe="/") for p in (self.root, request_id) if p
        )
        return f"{self.url}/{path}"

    @retry(
        stop=stop_after_attempt(3), wait=wait_random_exponential(max=60), reraise=True
    )
    def delete_collection_and_contents(self, request_id):
        """
        Remove a request's collection and everything in it. A collection that
        isn't there is not an error - there is nothing left to clean up.
        """
        response = requests.delete(
            self.collection_url(request_id), auth=self.auth, timeout=DELETE_TIMEOUT
        )
        if response.status_code == 404:
            return
        response.raise_for_status()
