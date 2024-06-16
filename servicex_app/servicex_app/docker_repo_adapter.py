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

import requests
from flask import current_app


class DockerRepoAdapter:
    def __init__(self, registry_endpoint="https://hub.docker.com"):
        self.registry_endpoint = registry_endpoint

    def check_image_exists(self, tagged_image: str) -> bool:
        """
        Checks that the given Docker image
        :param tagged_image: Full Docker image name, e.g. "sslhep/servicex_app:latest".
        :return: Whether or not the image exists in the registry.
        """
        search_result = re.search("(.+)/(.+):(.+)", tagged_image)
        if not search_result or len(search_result.groups()) != 3:
            return False

        (repo, image, tag) = search_result.groups()

        query = f'{self.registry_endpoint}/v2/repositories/{repo}/{image}/tags/{tag}'
        r = requests.get(query)
        if r.status_code == 404:
            return False

        current_app.logger.info(f"Requested Image: {tagged_image} exists, "
                                f"last updated {r.json()['last_updated']}")
        return True
