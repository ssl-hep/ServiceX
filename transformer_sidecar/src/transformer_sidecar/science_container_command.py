# Copyright (c) 2024, IRIS-HEP
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
import json
import logging
import os
import socket
from typing import Optional

# Transforms can run for a very long time, so we only give up on the science
# container after it has been silent for many hours.
DEFAULT_TIMEOUT = 12 * 60 * 60


class ScienceContainerException(Exception):
    pass


class ScienceContainerCommand:
    def __init__(self, request_id: str = "", timeout: Optional[float] = None):
        handler = logging.NullHandler()
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(handler)
        self.request_id = request_id
        self.timeout = (
            timeout
            if timeout is not None
            else float(os.environ.get("SCIENCE_CONTAINER_TIMEOUT", DEFAULT_TIMEOUT))
        )
        self.conn = None
        self.addr = None

        # Open a socket for the science container. We bind and listen right away so
        # the science container can connect as soon as it is up, and only wait for
        # it to show up in accept()
        self.serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serv.bind(("localhost", 8081))
        self.serv.listen()

    def accept(self):
        self.conn, self.addr = self.serv.accept()
        self.conn.settimeout(self.timeout)

    def _recv(self) -> bytes:
        try:
            return self.conn.recv(4096)
        except socket.timeout as e:
            self.logger.error(
                "timed out waiting for the science container",
                extra={"request_id": self.request_id},
            )
            raise ScienceContainerException(
                "timed out waiting for the science container"
            ) from e

    def synch(self):
        while True:
            self.logger.debug(
                "waiting for the GeT", extra={"request_id": self.request_id}
            )
            req = self._recv()
            if not req:
                self.logger.error(
                    "problem in getting GeT", extra={"request_id": self.request_id}
                )
                raise ScienceContainerException("problem in getting GeT")
            req1 = req.decode("utf8")
            self.logger.debug(
                f"REQ >>>>>>>>>>>>>>>{req1}", extra={"request_id": self.request_id}
            )
            if req1.startswith("GeT"):
                break

    def send(self, transform_request: dict):
        res = json.dumps(transform_request) + "\n"
        self.logger.debug(f"sending: {res}", extra={"request_id": self.request_id})
        self.conn.send(res.encode())

    def await_response(self):
        self.logger.debug(
            "WAITING FOR STATUS...", extra={"request_id": self.request_id}
        )
        req = self._recv()
        if not req:
            self.logger.error(
                "problem in getting the status", extra={"request_id": self.request_id}
            )
            raise ScienceContainerException("problem in getting the status")
        req2 = req.decode("utf8").strip()
        self.logger.debug(
            f"STATUS RECEIVED: {req2}", extra={"request_id": self.request_id}
        )
        return req2

    def confirm(self):
        self.conn.send("confirmed.\n".encode())

    def close(self):
        self.conn.send("stop.\n".encode())
        self.conn.close()
        self.serv.close()
