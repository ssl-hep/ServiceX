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
"""
Prometheus instrumentation for the ServiceX App.

It serves the exporter's default HTTP metric families on ``/metrics``.

gunicorn serves the app from several worker processes, and a scrape only
reaches whichever worker answered it. ``prometheus_client``'s multiprocess mode
handles that: each worker accumulates its metrics in mmap files under
``PROMETHEUS_MULTIPROC_DIR`` and the scraped worker sums across all of them.
``boot.sh`` creates that directory and ``gunicorn.conf.py`` retires the files
of workers that have exited. Without the environment variable -- a single
process ``flask run``, or the test suite -- the plain in-process exporter is
used instead.

The endpoint is unauthenticated, and ``/`` is routed to the app by the
ingress, so it is reachable from outside the cluster when the ingress is on.
It is off unless ``ENABLE_METRICS`` is set, which the Helm chart does only when
monitoring is switched on.
"""

import os
from typing import Optional

METRICS_PATH = "/metrics"


def _multiprocess_dir() -> Optional[str]:
    """The mmap directory shared by the gunicorn workers, if configured."""
    return os.environ.get("PROMETHEUS_MULTIPROC_DIR") or os.environ.get(
        "prometheus_multiproc_dir"
    )


def init_metrics(app):
    """Attach the Prometheus exporter and its ``/metrics`` endpoint to ``app``.

    Safe to call more than once on the same process: the exporter's own
    ``export_defaults`` swallows the duplicate-registration error, which is
    what repeated ``create_app()`` calls in the test suite would otherwise hit.

    :param app: the Flask application to instrument.
    :return: the exporter, or ``None`` when metrics are switched off or the
        ``prometheus_flask_exporter`` dependency is missing.
    """
    if not app.config.get("ENABLE_METRICS", False):
        app.logger.info("Prometheus metrics are disabled (ENABLE_METRICS)")
        return None

    multiproc_dir = _multiprocess_dir()

    try:
        if multiproc_dir:
            # Has to exist before the exporter is constructed -- it validates
            # the directory rather than creating it.
            os.makedirs(multiproc_dir, exist_ok=True)
            from prometheus_flask_exporter.multiprocess import (
                GunicornInternalPrometheusMetrics as Exporter,
            )
        else:
            from prometheus_flask_exporter import PrometheusMetrics as Exporter
    except ImportError:
        app.logger.error(
            "ENABLE_METRICS is set but prometheus-flask-exporter is not "
            "installed; no metrics will be served."
        )
        return None

    metrics = Exporter(app, path=METRICS_PATH, group_by="url_rule")

    app.logger.info(
        "Prometheus metrics available at %s (multiprocess dir: %s)",
        METRICS_PATH,
        multiproc_dir or "not in use",
    )
    return metrics
