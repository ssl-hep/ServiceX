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
import re


class DIDParser:
    # RE to find the first scheme reference and add any remaining ones into the did
    did_re = re.compile("^(\\w+):\\/\\/(.*$)")

    def __init__(self, did: str, default_scheme: str = 'rucio'):
        """
        Parse the did and extract the scheme. If no scheme is found, default to the
        provided one
        :param did: Full DID which may contain a scheme
        :param default_scheme: Use this if no scheme provided
        """
        match = self.did_re.match(did)
        if match:
            self.scheme = match.group(1)
            self.did = match.group(2)
        else:
            self.scheme = default_scheme
            self.did = did

    @property
    def microservice_queue(self) -> str:
        """
        Construct the name of the rabbit queue that will feed the did finder based
        on the scheme name
        :return: queue name
        """
        return f"{self.scheme}_did_requests"

    @property
    def full_did(self) -> str:
        """
        Reconstruct the full DID with scheme - this is useful if the scheme was defaulted
        :return:
        """
        return f'{self.scheme}://{self.did}'
