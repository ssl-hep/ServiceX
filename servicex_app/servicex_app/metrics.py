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

Exposes an unauthenticated ``/metrics`` endpoint carrying two families of data:

* HTTP request counters/histograms, contributed automatically by
  ``prometheus_flask_exporter``.
* ServiceX domain gauges (transform requests by status, datasets by lookup
  status, user counts), refreshed from PostgreSQL immediately before each
  scrape is rendered.

The app is served by gunicorn with several worker processes, so
``prometheus_client`` has to run in multiprocess mode: every worker writes into
mmap files under ``PROMETHEUS_MULTIPROC_DIR`` and the scraped worker aggregates
across all of them. ``gunicorn.conf.py`` supplies the ``child_exit`` hook that
retires the files of a dead worker.

Exported series:

* ``servicex_app_http_request_total{method,status}``
* ``servicex_app_http_request_duration_seconds{method,status,url_rule}``
* ``servicex_transform_requests{status}``, ``servicex_transform_files{outcome}``
* ``servicex_datasets{lookup_status}``, ``servicex_users{state}``
"""
import os
from typing import Optional

from flask import request

METRICS_PATH = "/metrics"

_gauges = None


def _multiprocess_dir() -> Optional[str]:
    """The mmap directory shared by the gunicorn workers, if configured."""
    return os.environ.get("PROMETHEUS_MULTIPROC_DIR") or os.environ.get(
        "prometheus_multiproc_dir"
    )


def _app_version() -> str:
    """Same source as the /servicex info endpoint, without importing it."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("servicex_app")
    except PackageNotFoundError:
        return "develop"


def _build_gauges():
    """Declare the ServiceX domain gauges against the default registry."""
    from prometheus_client import Gauge

    mode = {"multiprocess_mode": "livemostrecent"} if _multiprocess_dir() else {}

    return {
        "info": Gauge(
            "servicex_app_info",
            "ServiceX App build information (always 1)",
            ["version", "instance"],
            **mode,
        ),
        "transform_requests": Gauge(
            "servicex_transform_requests",
            "Number of transform requests, by status",
            ["status"],
            **mode,
        ),
        "transform_files": Gauge(
            "servicex_transform_files",
            "Files seen across all transform requests, by outcome",
            ["outcome"],
            **mode,
        ),
        "datasets": Gauge(
            "servicex_datasets",
            "Number of datasets, by lookup status",
            ["lookup_status"],
            **mode,
        ),
        "users": Gauge(
            "servicex_users",
            "Number of user accounts, by state",
            ["state"],
            **mode,
        ),
    }


def _refresh_domain_metrics(app):
    """Re-read the ServiceX tables and publish the results onto the gauges.

    Any failure here must not break the scrape: Prometheus would then lose the
    HTTP metrics as well, which are the ones that matter when the database is
    the thing that is sick.
    """
    from sqlalchemy import func

    from servicex_app.models import (
        Dataset,
        DatasetStatus,
        TransformRequest,
        TransformStatus,
        UserModel,
        db,
    )

    try:
        counts = dict(
            db.session.query(TransformRequest.status, func.count(TransformRequest.id))
            .group_by(TransformRequest.status)
            .all()
        )
        for status in TransformStatus:
            _gauges["transform_requests"].labels(status=status.name).set(
                counts.get(status, 0)
            )

        files_completed, files_failed = db.session.query(
            func.coalesce(func.sum(TransformRequest.files_completed), 0),
            func.coalesce(func.sum(TransformRequest.files_failed), 0),
        ).one()
        _gauges["transform_files"].labels(outcome="completed").set(files_completed)
        _gauges["transform_files"].labels(outcome="failed").set(files_failed)

        dataset_counts = dict(
            db.session.query(Dataset.lookup_status, func.count(Dataset.id))
            .group_by(Dataset.lookup_status)
            .all()
        )
        for status in DatasetStatus:
            _gauges["datasets"].labels(lookup_status=status.name).set(
                dataset_counts.get(status, 0)
            )

        pending = (
            db.session.query(func.count(UserModel.id))
            .filter(UserModel.pending.is_(True))
            .scalar()
        )
        total = db.session.query(func.count(UserModel.id)).scalar()
        _gauges["users"].labels(state="pending").set(pending)
        _gauges["users"].labels(state="approved").set(total - pending)
    except Exception:
        app.logger.exception("Failed to refresh ServiceX metrics from the database")
        db.session.rollback()


def init_metrics(app):
    """Attach the Prometheus exporter and ``/metrics`` endpoint to ``app``.

    Returns the exporter, or ``None`` when metrics are disabled or the
    ``prometheus_flask_exporter`` dependency is unavailable.
    """
    global _gauges

    if not app.config.get("ENABLE_METRICS", True):
        app.logger.info("Prometheus metrics disabled by configuration")
        return None

    multiproc_dir = _multiprocess_dir()

    if multiproc_dir:
        from prometheus_flask_exporter.multiprocess import (
            GunicornInternalPrometheusMetrics as Exporter,
        )
    else:
        from prometheus_flask_exporter import PrometheusMetrics as Exporter

    if multiproc_dir:
        os.makedirs(multiproc_dir, exist_ok=True)

    metrics = Exporter(
        app,
        path=METRICS_PATH,
        group_by="url_rule",
        defaults_prefix="servicex_app",
        excluded_paths=[METRICS_PATH],
    )

    if _gauges is None:
        _gauges = _build_gauges()

    _gauges["info"].labels(
        version=_app_version(),
        instance=os.environ.get("INSTANCE_NAME", "Unknown"),
    ).set(1)

    @app.before_request
    def _refresh_metrics_before_scrape():
        if request.path == METRICS_PATH:
            _refresh_domain_metrics(app)

    app.logger.info(
        "Prometheus metrics available at %s (multiprocess dir: %s)",
        METRICS_PATH,
        multiproc_dir or "disabled",
    )
    return metrics
