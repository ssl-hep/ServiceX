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
from urllib.parse import quote

from flask import current_app

from servicex_app.reliable_requests import servicex_retry, REQUEST_TIMEOUT


class DockerRepoAdapter:
    @servicex_retry()
    def get_image_by_tag(
        self, repo: str, image: str, tag: str, registry: str
    ) -> requests.Response:
        if registry == "docker.io":
            return self._dockerhub_get_image_by_tag(repo, image, tag)

        if registry == "gitlab-registry.cern.ch":
            return self._cern_gitlab_get_image_by_tag(repo, image, tag)

        raise ValueError(f"Invalid registry: {registry}")

    def _dockerhub_get_image_by_tag(
        self, repo: str, image: str, tag: str
    ) -> requests.Response:
        query = f"https://hub.docker.com/v2/repositories/{repo}/{image}/tags/{tag}"
        return requests.get(query, timeout=REQUEST_TIMEOUT)

    def _cern_gitlab_get_image_by_tag(
        self, repo: str, image: str, tag: str
    ) -> requests.Response:
        project_name = f"{repo}/{image}"
        project_id = quote(project_name, safe="")

        repositories_query = (
            f"https://gitlab.cern.ch/api/v4/projects/{project_id}/registry/repositories"
        )
        repositories_request = requests.get(repositories_query, timeout=REQUEST_TIMEOUT)
        repositories = repositories_request.json()

        repository_id = None
        for repository in repositories:
            if repository["path"] == project_name:
                repository_id = repository["id"]
                break

        if repository_id is None:
            raise ValueError(f"repository {project_name} not found")

        query = (
            "https://gitlab.cern.ch/api/v4/"
            f"projects/{project_id}/registry/repositories/{repository_id}/tags/{tag}"
        )
        return requests.get(query, timeout=REQUEST_TIMEOUT)

    def check_image_exists(self, tagged_image: str) -> bool:
        """
        Checks that the given Docker image
        :param tagged_image: Full Docker image name, e.g. "sslhep/servicex_app:latest".
        :return: Whether or not the image exists in the registry.
        """
        registry = self._parse_docker_registry(tagged_image)
        if registry == "docker.io":
            search_result = re.search("(.+)/(.+):(.+)", tagged_image)
        else:
            stripped_image = tagged_image.removeprefix(registry + "/")
            search_result = re.search("(.+)/(.+):(.+)", stripped_image)

        if not search_result or len(search_result.groups()) != 3:
            return False

        (repo, image, tag) = search_result.groups()

        try:
            r = self.get_image_by_tag(repo, image, tag, registry)
        except ValueError:
            return False

        if r.status_code != 200:
            return False

        current_app.logger.info(
            f"Requested Image: {tagged_image} exists, "
            f"last updated {r.json().get('last_updated', 'unknown')}"
        )
        return True

    def _parse_docker_registry(self, image: str):
        image = image.split("@", 1)[0]
        image = image.split(":", 1)[0] if "/" in image.split(":")[0] else image

        parts = image.split("/", 1)

        if len(parts) > 1 and (
            "." in parts[0] or ":" in parts[0] or parts[0] == "localhost"
        ):
            return parts[0]
        else:
            return "docker.io"
