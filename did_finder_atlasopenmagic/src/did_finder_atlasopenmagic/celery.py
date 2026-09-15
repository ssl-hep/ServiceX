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
from typing import Any, Dict, Generator
import atlasopenmagic as atom

from servicex_did_finder_lib import DIDFinderApp
from servicex_did_finder_lib.exceptions import (
    BadDatasetNameException,
    NoSuchDatasetException,
    LookupFailureException,
)
from servicex_did_finder_lib.logstash_logging import initialize_logging

__log = initialize_logging(component_name="atom_did_finder")

app = DIDFinderApp("atlasopenmagic")


@app.did_lookup_task(name="did_finder_atlasopenmagic.lookup_dataset")
def lookup_dataset(self, did: str, dataset_id: int, endpoint: str) -> None:
    self.do_lookup(
        did=did, dataset_id=dataset_id, endpoint=endpoint, user_did_finder=find_files
    )


def find_files(
    did_name: str, info: Dict[str, Any], did_finder_args: dict = None
) -> Generator[Dict[str, Any], None, None]:
    """
    For each incoming did name, generate a list of files that ServiceX can process

    Args:
        did_name (str): Dataset specification, in the format <release>/<id> or
                        <release>/<id>/<skim>
        info (Dict[str, Any]): Information bag, mainly has the `request-id` which is
                               used to track error mesages accross logs.
        did_finder_args (dict): Additional arguments passed to the finder
    Returns:
        Generator[Dict[str, any], None]: yield each file
    """

    if did_name.count("/") not in (1, 2):
        raise BadDatasetNameException(
            "Dataset must be specified in the form <release>/<id> or <release>/<id>/<skim>"
        )

    match did_name.split("/"):
        case [release, did]:
            skim = "noskim"
        case [release, did, skim]:
            pass

    try:
        atom.set_release(release)
    except ValueError as e:
        raise NoSuchDatasetException(f"Invalid release. Error: {e}") from e

    if did not in atom.available_datasets():
        raise NoSuchDatasetException(
            f"Dataset ID {did} not found for release {release}"
        )

    if skim != "noskim" and skim not in atom.available_skims():
        raise NoSuchDatasetException(f"Skim {skim} not found for release {release}")

    try:
        for url in atom.get_urls(key=did, skim=skim, protocol="root"):
            yield {
                "paths": [url],
                "adler32": 0,  # No clue
                "file_size": 0,  # Size in bytes if known
                "file_events": 0,  # Number of events if known
            }
    except Exception as e:
        raise LookupFailureException(f"Lookup failure: {e}") from e
