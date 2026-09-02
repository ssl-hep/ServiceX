"""Gunicorn configuration for the ServiceX App.

Both hooks here exist because gunicorn forks its workers, and the observability
SDKs care which side of the fork they are initialised on.
"""

import os


def post_fork(server, worker):
    """Start OpenTelemetry inside the freshly forked worker.

    The SDK must be built after the fork: a provider created in the arbiter
    would give every worker a BatchSpanProcessor whose exporter thread did not
    survive. Gunicorn runs this before the worker loads the WSGI app, so the
    class-level Flask and SQLAlchemy instrumentation is in place by the time
    `create_app()` runs.
    """
    from servicex_app.tracing import init_tracing

    init_tracing(os.environ.get("OTEL_SERVICE_NAME", "servicex-app"))


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
