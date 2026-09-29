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
"""Prometheus metrics for the transformer sidecar.

The sidecar sits between the science container and ServiceX, so it already
sees everything worth counting: how long the science container took per
replica, how many events came out, how big the result was, how long the upload
took. This module declares those as Prometheus metrics and serves them on an
HTTP port so the bundled Prometheus can scrape each transformer pod.

The transformer pod is identified by the ``pod``/``service`` labels Prometheus
attaches during discovery, so the request id is only carried on the ``_info``
gauge rather than on every series.
"""
import logging
import os

from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)

FILES = Counter(
    "servicex_transformer_files_total",
    "Files this transformer has finished with, by outcome",
    ["outcome"],
)

FILE_SECONDS = Histogram(
    "servicex_transformer_file_seconds",
    "Wall time from receiving a file until its completion was reported, by outcome",
    ["outcome"],
    buckets=(5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600, 7200),
)

FILES_IN_PROGRESS = Gauge(
    "servicex_transformer_files_in_progress",
    "Files currently being transformed",
)

REPLICA_ATTEMPTS = Counter(
    "servicex_transformer_replica_attempts_total",
    "Replicas handed to the science container, by result",
    ["result"],
)

SCIENCE_SECONDS = Histogram(
    "servicex_transformer_science_seconds",
    "Wall time the science container spent on a single replica",
    buckets=(5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600, 7200),
)

UPLOAD_SECONDS = Histogram(
    "servicex_transformer_upload_seconds",
    "Time to upload one result file to the object store",
    buckets=(0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)

EVENTS = Counter(
    "servicex_transformer_events_total",
    "Events reported by the science container for successful files",
)

OUTPUT_BYTES = Counter(
    "servicex_transformer_output_bytes_total",
    "Bytes of result files produced by successful transforms",
)

CONVERSION_FAILURES = Counter(
    "servicex_transformer_conversion_failures_total",
    "Sidecar-side format conversions that failed, by target format",
    ["format"],
)

CPU_SECONDS = Counter(
    "servicex_transformer_cpu_seconds_total",
    "CPU time consumed by the sidecar and its children while processing files",
    ["mode"],
)

INFO = Gauge(
    "servicex_transformer_info",
    "Transformer identity (always 1)",
    ["request_id", "instance", "site", "host"],
)


def record_cpu_times(user: float, system: float, iowait: float) -> None:
    """Add the per-file CPU deltas. iowait is -1 where psutil can't report it."""
    CPU_SECONDS.labels(mode="user").inc(max(user, 0))
    CPU_SECONDS.labels(mode="system").inc(max(system, 0))
    if iowait >= 0:
        CPU_SECONDS.labels(mode="iowait").inc(iowait)


def start(request_id: str, place: dict) -> bool:
    """Serve the metrics on ``METRICS_PORT`` if it is set.

    Returns True if the server was started. Must run in the process that
    executes the celery task, since the counters live in that process's memory.
    """
    port = int(os.environ.get("METRICS_PORT", "0") or 0)
    if not port:
        logger.info("METRICS_PORT not set; Prometheus metrics disabled")
        return False

    INFO.labels(
        request_id=request_id,
        instance=os.environ.get("INSTANCE_NAME", "Unknown"),
        site=place.get("site", "unknown"),
        host=place.get("host", "unknown"),
    ).set(1)

    # Prefer dual-stack like the app's gunicorn ([::]), but fall back for hosts
    # with IPv6 disabled.
    addr = os.environ.get("METRICS_ADDR", "::")
    try:
        start_http_server(port, addr=addr)
    except OSError:
        if addr != "0.0.0.0":
            addr = "0.0.0.0"
            start_http_server(port, addr=addr)
        else:
            raise

    logger.info(
        "Prometheus metrics available", extra={"metrics_port": port, "addr": addr}
    )
    return True
