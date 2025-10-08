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

from servicex_app.reliable_requests import servicex_retry, REQUEST_TIMEOUT


class DockerRepoAdapter:
    def __init__(self, registry_endpoint="https://hub.docker.com"):
        self.registry_endpoint = registry_endpoint

    @servicex_retry()
    def get_image_by_tag(self, repo: str, image: str, tag: str) -> requests.Response:
        query = f"{self.registry_endpoint}/v2/repositories/{repo}/{image}/tags/{tag}"
        r = requests.get(query, timeout=REQUEST_TIMEOUT)
        return r

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
        r = self.get_image_by_tag(repo, image, tag)

        if r.status_code == 404:
            return False

        current_app.logger.info(
            f"Requested Image: {tagged_image} exists, "
            f"last updated {r.json()['last_updated']}"
        )
        return True

    @servicex_retry()
    def get_image_manifest(self, repo: str, image: str, tag: str) -> requests.Response:
        """Get Docker image manifest from registry API v2."""
        # Try Docker Hub v2 API first for manifest
        query = f"https://registry-1.docker.io/v2/{repo}/{image}/manifests/{tag}"
        headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
        try:
            r = requests.get(query, headers=headers, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return r
        except Exception:
            pass

        # Fall back to Docker Hub v1 API for basic info
        query = f"{self.registry_endpoint}/v2/repositories/{repo}/{image}/tags/{tag}"
        r = requests.get(query, timeout=REQUEST_TIMEOUT)
        return r

    def get_image_info(self, tagged_image: str) -> dict:
        """
        Get detailed information about a Docker image including layers and configuration.

        :param tagged_image: Full Docker image name, e.g. "sslhep/servicex_app:latest"
        :return: Dictionary containing image metadata, layers, config, etc.
        """
        search_result = re.search("(.+)/(.+):(.+)", tagged_image)
        if not search_result or len(search_result.groups()) != 3:
            current_app.logger.warning(f"Invalid image format: {tagged_image}")
            return None

        (repo, image, tag) = search_result.groups()

        try:
            # Get manifest/detailed info
            r = self.get_image_manifest(repo, image, tag)

            if r.status_code != 200:
                current_app.logger.warning(
                    f"Failed to get image info for {tagged_image}: {r.status_code}"
                )
                return None

            manifest_data = r.json()

            # Extract relevant information depending on API version
            image_info = {
                "digest": manifest_data.get("digest"),
                "layers": [],
                "config": {},
                "history": [],
            }

            # Handle Docker Registry v2 manifest format
            if "layers" in manifest_data:
                image_info["layers"] = [
                    layer.get("digest", "") for layer in manifest_data["layers"]
                ]

            # Handle config blob reference
            if "config" in manifest_data:
                config_digest = manifest_data["config"].get("digest")
                if config_digest:
                    # For full implementation, we'd fetch the config blob here
                    # For now, store the reference
                    image_info["config"] = {"digest": config_digest}

            # Handle Docker Hub v1 API response format
            if "last_updated" in manifest_data:
                image_info["last_updated"] = manifest_data["last_updated"]

            # Add some basic metadata
            image_info["tag_info"] = manifest_data

            current_app.logger.debug(f"Retrieved image info for {tagged_image}")
            return image_info

        except Exception as e:
            current_app.logger.warning(
                f"Error retrieving image info for {tagged_image}: {str(e)}"
            )
            return None
