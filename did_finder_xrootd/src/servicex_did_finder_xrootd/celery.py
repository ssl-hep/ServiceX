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
import os
from servicex_did_finder_lib.logstash_logging import initialize_logging
from typing import Any, Dict, Generator
from XRootD import client as xrd

from servicex_did_finder_lib import DIDFinderApp
from servicex_did_finder_lib.exceptions import (
    NoSuchDatasetException,
    LookupFailureException,
)

__log = initialize_logging(component_name="xrootd_did_finder")

cache_prefix = os.environ.get("CACHE_PREFIX", "")
app = DIDFinderApp("xrootd")


@app.did_lookup_task(name="did_finder_xrootd.lookup_dataset")
def lookup_dataset(self, did: str, dataset_id: int, endpoint: str) -> None:
    self.do_lookup(
        did=did, dataset_id=dataset_id, endpoint=endpoint, user_did_finder=find_files
    )


def find_files(
    did_name: str, info: Dict[str, Any], did_finder_args: dict = None
) -> Generator[Dict[str, Any], None, None]:
    """For each incoming XRootD glob specification, generate a list of files that ServiceX can
    process

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
        urls = xrd.glob(cache_prefix + did_name, raise_error=True)
    except Exception as e:
        raise LookupFailureException(f"Failure searching for {did_name}: {e}") from e
    if len(urls) == 0:
        raise NoSuchDatasetException(
            f"No files found matching {did_name} for dataset "
            f"{info['dataset-id']} - are you sure it is correct?"
        )

    for url in urls:
        yield {
            "paths": [url],
            "adler32": 0,  # No clue
            "file_size": 0,  # We could look up the size but that would be slow
            "file_events": 0,  # And this we do not know
        }
