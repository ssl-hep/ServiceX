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
import socket


class ScienceContainerException(Exception):
    pass


class ScienceContainerCommand:
    def __init__(self):
        # Open a socket to the science container
        self.serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serv.bind(("localhost", 8081))
        self.serv.listen()
        self.conn, self.addr = self.serv.accept()

    def synch(self):
        while True:
            print("waiting for the GeT")
            req = self.conn.recv(4096)
            if not req:
                print("problem in getting GeT")
                raise ScienceContainerException("problem in getting GeT")
            req1 = req.decode("utf8")
            print("REQ >>>>>>>>>>>>>>>", req1)
            if req1.startswith("GeT"):
                break

    def send(self, transform_request: dict):
        res = json.dumps(transform_request) + "\n"
        print("sending:", res)
        self.conn.send(res.encode())

    def await_response(self):
        print("WAITING FOR STATUS...")
        req = self.conn.recv(4096)
        # if not req:
        #     break
        req2 = req.decode("utf8").strip()
        print("STATUS RECEIVED :", req2)
        return req2

    def confirm(self):
        self.conn.send("confirmed.\n".encode())

    def close(self):
        self.conn.send("stop.\n".encode())
        self.conn.close()
        self.serv.close()
