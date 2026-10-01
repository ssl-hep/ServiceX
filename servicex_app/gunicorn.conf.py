"""Gunicorn configuration for the ServiceX App.

Only the ``prometheus_client`` multiprocess bookkeeping needs a hook here.
Tracing sets itself up inside ``create_app()``, which gunicorn already runs in
the worker after the fork, so it needs no hook of its own.
"""

import os


def child_exit(server, worker):
    """Retire the exited worker's ``prometheus_client`` mmap files.

    Every worker accumulates its metrics in its own files under
    ``PROMETHEUS_MULTIPROC_DIR``. Counters and histograms are summed across all
    of those files whether or not the process that wrote them is still alive,
    which is correct -- a request the app served does not stop having happened.
    What this clears is the dead worker's live-mode gauge files, which would
    otherwise keep reporting a value for a process that no longer exists. It is
    the hook prometheus-flask-exporter documents for gunicorn deployments.
    """
    if not (
        os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        or os.environ.get("prometheus_multiproc_dir")
    ):
        return

    try:
        from prometheus_flask_exporter.multiprocess import (
            GunicornInternalPrometheusMetrics,
        )
    except ImportError:
        return

    GunicornInternalPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)
