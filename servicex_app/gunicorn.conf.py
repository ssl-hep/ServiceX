"""Gunicorn configuration for the ServiceX App."""

import os


def child_exit(server, worker):
    """Retire the exited worker's prometheus_client mmap files.

    Each worker accumulates metrics in its own files under
    `PROMETHEUS_MULTIPROC_DIR`; without this the files of a worker that dies are
    never cleaned up, and its final counter values are added to every
    subsequent scrape forever.
    """
    if not (
        os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        or os.environ.get("prometheus_multiproc_dir")
    ):
        return
    try:
        from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics

        GunicornPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)
    except ImportError:
        pass
