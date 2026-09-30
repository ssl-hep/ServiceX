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
import os

from celery.signals import worker_process_init
from rucio.client.didclient import DIDClient
from rucio.client.replicaclient import ReplicaClient

from rucio_did_finder.lookup_request import LookupRequest
from rucio_did_finder.rucio_adapter import RucioAdapter
from servicex_did_finder_lib import DIDFinderApp
from .replica_distance import ReplicaSorter

cache_prefix = os.environ.get("CACHE_PREFIX", "")
report_logical_files = os.environ.get("REPORT_LOGICAL_FILES", "0") == "1"


def make_rucio_adapter() -> RucioAdapter:
    """Build a RucioAdapter with its own Rucio clients and HTTP sessions."""
    return RucioAdapter(DIDClient(), ReplicaClient(), report_logical_files)


if (
    "RUCIO_LATITUDE" in os.environ
    and "RUCIO_LONGITUDE" in os.environ
    and "USE_REPLICA_SORTER" in os.environ
):
    location = {
        "latitude": float(os.environ["RUCIO_LATITUDE"]),
        "longitude": float(os.environ["RUCIO_LONGITUDE"]),
    }
    replica_sorter = ReplicaSorter()
else:
    location = None
    replica_sorter = None

rse_expression = os.environ.get("RUCIO_RSE_EXPRESSION")
if not rse_expression:
    raise ValueError(
        "RUCIO_RSE_EXPRESSION environment variable must be set to a Rucio RSE "
        "expression appropriate for this experiment's Rucio instance"
    )

ignore_availability = os.environ.get("RUCIO_IGNORE_AVAILABILITY", "false").lower() in (
    "true",
    "1",
    "yes",
)

# The rucio adapter is added to did_finder_args once per worker process
app = DIDFinderApp("rucio", did_finder_args={})


@worker_process_init.connect
def init_worker_process(**kwargs):
    """Give each prefork worker process its own Rucio clients.

    Building them at import time authenticated in the parent process and handed
    every child a copy of the same HTTP sessions across the fork.
    """
    app.did_finder_args["rucio_adapter"] = make_rucio_adapter()


def find_files(did_name, info, did_finder_args):
    # Pools that do not fork, such as solo, never send worker_process_init
    if "rucio_adapter" not in did_finder_args:
        did_finder_args["rucio_adapter"] = make_rucio_adapter()
    lookup_request = LookupRequest(
        did=did_name,
        rucio_adapter=did_finder_args["rucio_adapter"],
        dataset_id=info["dataset-id"],
        replica_sorter=replica_sorter,
        location=location,
        rse_expression=rse_expression,
        ignore_availability=ignore_availability,
    )
    for file in lookup_request.lookup_files():
        yield file


@app.did_lookup_task(name="did_finder_rucio.lookup_dataset")
def lookup_dataset(self, did: str, dataset_id: int, endpoint: str) -> None:
    self.do_lookup(
        did=did, dataset_id=dataset_id, endpoint=endpoint, user_did_finder=find_files
    )
