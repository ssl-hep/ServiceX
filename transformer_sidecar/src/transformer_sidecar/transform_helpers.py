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
"""Helpers shared by the Celery transformer (transformer.py) and the Temporal pilot.

Nothing here knows about Celery or Temporal. Log records get the pod's request id
from transformer_logging.RequestIdFilter, so call sites don't pass it.
"""

import json
import logging
import os
import re
import time
from hashlib import sha1, sha256
from pathlib import Path
from typing import NamedTuple, Optional

import psutil

from transformer_sidecar.transformer_stats import TransformerStats
from transformer_sidecar.transformer_stats.aod_stats import AODStats
from transformer_sidecar.transformer_stats.raw_uproot_stats import RawUprootStats
from transformer_sidecar.transformer_stats.topcp_stats import TopCPStats
from transformer_sidecar.transformer_stats.uproot_stats import UprootStats

logger = logging.getLogger(__name__)

# Use this to make sure we don't generate output file names that are crazy long
MAX_PATH_LEN = 255

# The stats parsers a transformer's capabilities file may name in "stats-parser"
STATS_PARSERS: dict[str, type[TransformerStats]] = {
    cls.__name__: cls for cls in (AODStats, RawUprootStats, TopCPStats, UprootStats)
}


class TimeTuple(NamedTuple):
    """
    Named tuple to store process time information.
    Immutable so values can't be accidentally altered after creation
    """

    user: float
    system: float
    iowait: float

    @property
    def total_time(self):
        """
        Return total time spent by process

        :return: sum of user, system, iowait times
        """
        return self.user + self.system + self.iowait


def get_process_info() -> TimeTuple:
    """
    Get process information (just cpu, sys, iowait times right now) and
    return it

    :return: TimeTuple with timing information
    """
    process_info = psutil.Process()
    time_stats = process_info.cpu_times()
    iowait = time_stats.iowait if hasattr(time_stats, "iowait") else -1
    return TimeTuple(
        user=time_stats.user + time_stats.children_user,
        system=time_stats.system + time_stats.children_system,
        iowait=iowait,
    )


def read_capabilities_file(shared_dir: str) -> dict:
    """
    The capabilities file is copied into the shared volume by the science container
    at startup. It's possible for the code to start before the file is available.
    We'll wait for it here.
    """
    logger.debug("Waiting for capabilities file")
    capabilities_file_path = Path(shared_dir, "transformer_capabilities.json")
    while not capabilities_file_path.is_file():
        time.sleep(1)

    with open(capabilities_file_path) as capabilities_file:
        return json.load(capabilities_file)


def prioritize_replicas(replicas: list[str]) -> list[str]:
    """
    Prioritizes a list of replicas by placing root replicas (those not starting
    with "http") before HTTP replicas.

    Args:
        replicas (list[str]): A list of replica URLs or paths.

    Returns:
        list[str]: The prioritized list of replicas, with root replicas first and
                    HTTP replicas second.
    """
    http_replicas = [replica for replica in replicas if replica.startswith("http")]
    root_replicas = [replica for replica in replicas if not replica.startswith("http")]
    return root_replicas + http_replicas


def change_davs_to_https(replicas: list[str]) -> list[str]:
    """
    Converts all replica URLs in the provided list that start with "davs" to use
    "https" instead.

    Args:
        replicas (list[str]): A list of replica URLs or paths.

    Returns:
        list[str]: A list of replica URLs with "davs" replaced by "https" at the
        start of each string.
    """
    return [re.sub("^davs", "https", _) for _ in replicas]


def prepend_xcache(file_paths: list[str]) -> list[str]:
    """
    If a CACHE_PREFIX is given, prepend the file paths with the xcache. If there
    are multiple xcaches, the same file will always be prepended with the same
    xcache. We do this by hashing the file path and then calculating modulo of the
    value.
    """
    prefix = os.environ.get("CACHE_PREFIX", "")

    if not prefix:
        return file_paths

    prefix_list = [p.strip() for p in prefix.split(",")]

    prefixed_paths = []
    for f in file_paths:
        # for each path we get unique hash value
        hex_digest = sha256(f.encode()).hexdigest()

        # we turn file hex_digest into an integer then calculate modulo of the
        # value.
        pinned_xcache_index = int(hex_digest, 16) % len(prefix_list)

        # Construct the path
        prefixed_paths.append(f"root://{prefix_list[pinned_xcache_index]}//{f}")
    return prefixed_paths


def order_replicas(replicas: list[str]) -> list[str]:
    """The replicas in the order to try them, with the xcache prefix if any."""
    return prepend_xcache(prioritize_replicas(change_davs_to_https(replicas)))


def hash_path(file_name: str) -> str:
    """
    Make the path safe for object store or POSIX, by keeping the length
    less than MAX_PATH_LEN. Replace the leading (less interesting) characters with a
    forty character hash.
    :param file_name: Input filename
    :return: Safe path string
    """
    if len(file_name) > MAX_PATH_LEN:
        hashed_value = sha1(file_name.encode("utf-8")).hexdigest()
        return "".join(
            [
                "_",
                hashed_value,
                file_name[-1 * (MAX_PATH_LEN - len(hashed_value) - 1) :],  # noqa: E203
            ]
        )
    else:
        return file_name


def fill_stats_parser(stats_parser_name: str, logfile_path: Path) -> TransformerStats:
    return STATS_PARSERS[stats_parser_name](logfile_path)


def convert_to_parquet(source_path: Path) -> Optional[Path]:
    """
    Convert a ROOT file to Parquet.  Returns the path to the Parquet file if successful,
    """
    import uproot
    import awkward as ak

    logger.info("Converting ROOT to Parquet.", extra={"input_path": str(source_path)})
    try:
        with open(source_path, "rb") as datafile:
            data = uproot.open(datafile)
            if len(data.keys(cycle=False)) != 1:
                logger.error(f"Expected one tree found {data.keys()}")
                return None
            tree_name = data.keys()[0]
            all_data = data[tree_name].arrays(library="ak")

            parquet_file = source_path.with_suffix(".parquet")

            # Save to temp file in same directory as parquet_file. The to_parquet
            # method doesn't plqy well with long paths.
            temp_file = Path(parquet_file.parent, "temp.parquet")
            ak.to_parquet(all_data, temp_file.as_posix())
            temp_file.rename(parquet_file)

    except Exception as e:
        logger.error(f"Failed to convert ROOT to Parquet: {e}")
        return None

    return parquet_file


def convert_to_rntuple(source_path: Path) -> Optional[Path]:
    """
    Convert a ROOT TTree file to RNTuple.  Returns the path to the output ROOT file if successful
    """
    import uproot

    logger.info(
        "Converting ROOT TTree to RNTuple.", extra={"input_path": str(source_path)}
    )

    rntuple_file = source_path.with_suffix(".rntuple.root")

    try:
        with open(source_path, "rb") as datafile:
            data = uproot.open(datafile)
            with open(rntuple_file, "b+w") as wfile:
                with uproot.recreate(wfile) as writer:
                    for key in data.keys(cycle=False):
                        obj = data[key]
                        match obj.classname:
                            case "TTree" | "ROOT::RNTuple":
                                for all_data in obj.iterate(library="ak"):
                                    if key not in writer:
                                        writer.mkrntuple(key, all_data)
                                    else:
                                        writer[key].extend(all_data)
                            case _:
                                writer[key] = obj

    except Exception as e:
        logger.error(f"Failed to convert ROOT TTree to RNTuple: {e}")
        return None

    return rntuple_file
