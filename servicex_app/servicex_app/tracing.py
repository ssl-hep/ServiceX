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
OpenTelemetry tracing for the ServiceX App.

Spans are exported over OTLP to Tempo, which the chart can deploy alongside
Prometheus and Grafana. Instrumentation covers the whole transform-submission
path: the inbound Flask request, its SQLAlchemy queries, the outbound calls to
the code generators and DID finders, and the Celery task that picks the work up
afterwards.

Two processes need initialising, and neither can do it at import time:

* **gunicorn workers.** The SDK must be created *after* the fork, or every
  worker inherits one BatchSpanProcessor thread from the parent that no longer
  runs. ``gunicorn.conf.py`` calls :func:`init_tracing` from ``post_fork``,
  which gunicorn runs before it loads the WSGI app -- so we instrument the
  ``Flask`` and ``Engine`` classes rather than instances, and ``create_app()``
  is traced by the time it runs.
* **Celery workers.** The prefork pool forks per child, so
  ``server_tasks.py`` re-initialises on the ``worker_process_init`` signal.

Tracing is off unless ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, which the Helm
chart only does when ``monitoring.tracing.enabled`` is true.
"""
import logging
import os
import socket

logger = logging.getLogger(__name__)

_initialised = False

_ESCAPING_EXC = "_servicex_escaping_exception_id"


class _SpanExceptionHandler(logging.Handler):
    """Attaches logged exceptions to the span that is currently recording.

    ServiceX resources overwhelmingly catch their own errors and turn them into
    a 500 response::

        except Exception as eek:
            current_app.logger.exception("...")
            return {"message": ...}, 500

    Nothing propagates out of the view, so the Flask instrumentation never sees
    an exception and the span carries no stack trace -- only an ERROR status
    inferred from the response code. Bridging the log record onto the span puts
    the traceback in Tempo without touching any of the call sites.

    The span status is deliberately left alone: a logged exception the code
    recovered from should not mark an otherwise successful request as failed.
    The HTTP status code already drives that.
    """

    def emit(self, record):
        if not record.exc_info:
            return
        exc = record.exc_info[1]
        if exc is None:
            return
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if not span.is_recording():
                return
            if getattr(span, _ESCAPING_EXC, None) == id(exc):
                return
            span.record_exception(exc)
        except Exception:
            pass


def _mark_escaping_exception(sender, exception, **extra):
    """`got_request_exception` receiver: flag exceptions Flask will re-report."""
    from opentelemetry import trace

    span = trace.get_current_span()
    if span.is_recording():
        setattr(span, _ESCAPING_EXC, id(exception))


def tracing_enabled() -> bool:
    """Whether the OTLP endpoint is configured and the SDK is not disabled."""
    if os.environ.get("OTEL_SDK_DISABLED", "").lower() == "true":
        return False
    return bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))


def init_tracing(service_name: str) -> bool:
    """Set up the tracer provider and instrument the libraries we care about.

    Safe to call from any process and safe to call when tracing is switched off
    or the OpenTelemetry packages are absent -- it returns ``False`` instead of
    raising, because a missing tracing backend must never stop the app booting.

    :param service_name: value for the ``service.name`` resource attribute,
        which is what Grafana groups by in the service graph.
    :return: ``True`` if tracing was activated in this process.
    """
    global _initialised

    if _initialised or not tracing_enabled():
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.error(
            "OTEL_EXPORTER_OTLP_ENDPOINT is set but the OpenTelemetry packages "
            "are not installed; tracing is disabled. Rebuild the servicex_app "
            "image to pick up the dependencies."
        )
        return False

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": os.environ.get("INSTANCE_NAME", "servicex"),
            "service.instance.id": os.environ.get("HOSTNAME", socket.gethostname()),
        }
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    _instrument_libraries(service_name)

    handler = _SpanExceptionHandler(level=logging.ERROR)
    root = logging.getLogger()
    if not any(isinstance(h, _SpanExceptionHandler) for h in root.handlers):
        root.addHandler(handler)

    _initialised = True
    logger.info(
        "Tracing enabled for %s, exporting to %s",
        service_name,
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"],
    )
    return True


def instrument_flask_app(app) -> bool:
    """Instrument one Flask application object.

    This has to be per-instance rather than the class-level
    ``FlaskInstrumentor().instrument()``, because that swaps out
    ``flask.Flask`` and ``servicex_app/__init__.py`` has already done
    ``from flask import Flask`` by then -- importing anything from this package
    binds the original class, so ``create_app()`` would build an uninstrumented
    app and no server spans would ever be produced.

    :return: ``True`` if this app is now instrumented.
    """
    if not tracing_enabled():
        return False

    try:
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
    except ImportError:
        return False

    if getattr(app, "_is_instrumented_by_opentelemetry", False):
        return True

    try:
        FlaskInstrumentor().instrument_app(
            app,
            excluded_urls="/metrics,/healthz",
        )
    except Exception:
        app.logger.exception("Failed to instrument Flask app for tracing")
        return False

    try:
        from flask import got_request_exception

        got_request_exception.connect(_mark_escaping_exception, app)
    except Exception:
        app.logger.exception("Could not connect got_request_exception receiver")

    return True


def _instrument_libraries(service_name: str) -> None:
    """Patch the instrumented libraries at class level.

    Each instrumentor is optional and independent: a missing or failing one is
    logged and skipped so the rest of the tracing still works.
    """
    instrumentors = [
        (
            "sqlalchemy",
            "opentelemetry.instrumentation.sqlalchemy",
            "SQLAlchemyInstrumentor",
            {},
        ),
        (
            "requests",
            "opentelemetry.instrumentation.requests",
            "RequestsInstrumentor",
            {},
        ),
    ]

    if "celery" in service_name:
        instrumentors.append(
            ("celery", "opentelemetry.instrumentation.celery", "CeleryInstrumentor", {})
        )

    for label, module_path, class_name, kwargs in instrumentors:
        try:
            module = __import__(module_path, fromlist=[class_name])
            getattr(module, class_name)().instrument(**kwargs)
        except ImportError:
            logger.warning("No OpenTelemetry instrumentation for %s installed", label)
        except Exception:
            logger.exception("Failed to instrument %s", label)
