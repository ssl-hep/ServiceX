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
import datetime
import logging
import os

import requests

from retry.api import retry_call
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

MAX_RETRIES = 3
RETRY_DELAY = 2


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
        self.session.mount('http://', HTTPAdapter(max_retries=retries))

    def post_status_update(self, file_id, status_code, info):
        doc = {
            "timestamp": datetime.datetime.now().isoformat(),
            "status-code": status_code,
            "pod-name": os.environ['POD_NAME'],
            "info": info
        }

        try:
            retry_call(self.session.post,
                       fargs=[self.server_endpoint + "/" + str(file_id) + "/status"],
                       fkwargs={"data": doc},
                       tries=MAX_RETRIES,
                       delay=RETRY_DELAY)
        except requests.exceptions.ConnectionError:
            self.logger.exception("Connection Error in post_status_update")

    def put_file_complete(self, file_path, file_id, status,
                          num_messages=None, total_time=None, total_events=None,
                          total_bytes=None):
        avg_rate = 0 if not total_time else int(total_events / total_time)
        doc = {
            "file-path": file_path,
            "file-id": file_id,
            "status": status,
            "num-messages": num_messages,
            "total-time": total_time,
            "total-events": total_events,
            "total-bytes": total_bytes,
            "avg-rate": avg_rate
        }

        self.logger.info("Put file complete.", extra=doc)

        if self.server_endpoint:
            try:
                retry_call(self.session.put,
                           fargs=[self.server_endpoint + "/file-complete"],
                           fkwargs={"json": doc},
                           tries=MAX_RETRIES,
                           delay=RETRY_DELAY)
            except requests.exceptions.ConnectionError:
                self.logger.exception("Connection Error in put_file_complete")
