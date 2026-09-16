# Copyright (c) 2026, IRIS-HEP
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
import os
from servicex_did_finder_lib.logstash_logging import initialize_logging
from typing import Any, Dict, Generator

from httpx import Client, Timeout
from httpx_retries import RetryTransport, Retry

from servicex_did_finder_lib import DIDFinderApp
from servicex_did_finder_lib.exceptions import (
    NoSuchDatasetException,
    LookupFailureException,
)

__log = initialize_logging(component_name="servicex_did_finder")

cache_prefix = os.environ.get("CACHE_PREFIX", "")
servicex_endpoint = os.environ["SERVICEX_ENDPOINT"]

app = DIDFinderApp("servicex")


@app.did_lookup_task(name="did_finder_servicex.lookup_dataset")
def lookup_dataset(self, did: str, dataset_id: int, endpoint: str) -> None:
    self.do_lookup(
        did=did, dataset_id=dataset_id, endpoint=endpoint, user_did_finder=find_files
    )


def find_files(
    did_name: str, info: Dict[str, Any], did_finder_args: Dict | None = None
) -> Generator[Dict[str, Any], None, None]:
    """For each incoming ServiceX transform ID, get the URLs

    Notes:

    Args:
        did_name (str): Dataset name
        info (Dict[str, Any]): Information bag, mainly has the `request-id` which is
                               used to track error mesages accross logs.
        did_finder_args (dict): Additional arguments passed to the finder

    Returns:
        Generator[Dict[str, any], None]: yield each file
    """
    __log.info(
        "DID Lookup request received.",
        extra={"dataset_id": info["dataset-id"], "dataset_name": did_name},
    )

    try:
        retry_options = Retry(total=3, backoff_factor=10)
        with Client(
            transport=RetryTransport(retry=retry_options),
            timeout=Timeout(10, read=300),
        ) as session:
            service_url = (
                servicex_endpoint
                + f"/servicex/internal/transformation/{did_name}/results"
            )
            r = session.get(url=service_url)
            if r.status_code != 200:
                raise LookupFailureException(
                    f"Failure searching for {did_name}: {r.status_code}"
                )
            transform_data = r.json()["results"]
            file_list = [
                (_["s3-object-name"], _["total-bytes"])
                for _ in transform_data
                if _["transform_status"] == "success"
            ]

            service_url = (
                servicex_endpoint + "/servicex/internal/transformation/file-urls"
            )
            r = session.post(
                service_url, json={"request_id": did_name, "file_list": file_list}
            )
            if r.status_code == 404:
                raise NoSuchDatasetException(f"Results for {did_name} not found")

            url_data = r.json()["uris"]
            res = []
            for f, size in file_list:
                _file = (
                    url_data[f][0],
                    size,
                )
                res.append(_file)
    except NoSuchDatasetException as e:
        raise e
    except Exception as e:
        raise LookupFailureException(f"Failure searching for {did_name}: {e}")

    for data in res:
        yield {
            "paths": [data[0]],
            "adler32": 0,  # No clue
            "file_size": data[1],  # We could look up the size but that would be slow
            "file_events": 0,  # And this we do not know
        }
