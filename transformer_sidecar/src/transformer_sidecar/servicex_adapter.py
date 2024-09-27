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
from typing import Any

import requests
import os

from retry.api import retry_call
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter


MAX_RETRIES = 3
RETRY_DELAY = 2

PLACE = {
    "host_name": os.getenv("HOST_NAME", "unknown"),
    "site": os.getenv("site", "unknown")
}


class FileCompleteRecord:
    def __init__(self, request_id: str, file_path: str, file_id: int, status: str,
                 total_time: float, total_events: int, total_bytes: int):
        assert request_id, "request_id is required"
        assert file_path, "file_path is required"
        assert file_id, "file_id is required"
        assert status, "status is required"

        self.request_id = request_id
        self.file_path = file_path
        self.file_id = file_id
        self.status = status
        self.total_time = total_time
        self.total_events = total_events
        self.total_bytes = total_bytes
        self.avg_rate = total_events / total_time if total_time else 0

    def to_json(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "file-path": self.file_path,
            "file-id": self.file_id,
            "status": self.status,
            "total-time": self.total_time,
            "total-events": self.total_events,
            "total-bytes": self.total_bytes,
            "avg-rate": self.avg_rate,
            "place": PLACE
        }


class ServiceXAdapter:
    def __init__(self, servicex_endpoint, logger=None):
        # Default logger doesn't print so that code that uses library
        # can override

        handler = logging.NullHandler()
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(handler)

        self.server_endpoint = servicex_endpoint
        self.session = requests.session()

        retries = Retry(total=5,
                        connect=3,
                        backoff_factor=0.1)
        self.session.mount('http', HTTPAdapter(max_retries=retries))

    def put_file_complete(self, rec: FileCompleteRecord):
        if self.server_endpoint:
            try:
                retry_call(self.session.put,
                           fargs=[self.server_endpoint + "/file-complete"],
                           fkwargs={"json": rec.to_json(), "timeout": (0.5, None)},
                           tries=MAX_RETRIES,
                           delay=RETRY_DELAY)
                self.logger.info("Put file complete.", extra={'requestId': rec.request_id,
                                                              "place": PLACE,
                                                              "file_path": rec.file_path})
            except requests.exceptions.ConnectionError:
                self.logger.exception("Connection Error in put_file_complete",
                                      extra={'requestId': rec.request_id,
                                             "place": PLACE}
                                      )
