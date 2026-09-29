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
"""OpenTelemetry tracing for the transformer sidecar.

The app's Celery worker is instrumented, so every ``transform_file`` message it
queues carries trace context in its headers. Instrumenting Celery here means the
sidecar's task span joins the trace that began with the user's API call, and
the ``put_file_complete`` call back to the app (via ``requests``) is linked the
same way.

On top of the automatic spans, :func:`record_transform_failure` copies what the
sidecar knows about a failed file -- the parsed error and the tail of the
science container's log -- onto the task span, so a failed transform can be
diagnosed from Tempo without hunting for the pod's logs.

Tracing is on precisely when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, which the
app does when launching transformer pods with tracing enabled.
"""
import logging
import os
import socket

logger = logging.getLogger(__name__)

_initialised = False

# How much of the science container's log to keep on a failure event. Spans go
# to Tempo in one OTLP message, so this is bounded; the end of the log is where
# the traceback and the sidecar's own diagnosis are.
SCIENCE_LOG_TAIL_BYTES = 16_000

FAILURE_EVENT = "transform.failure"


class _SpanExceptionHandler(logging.Handler):
    """Attach exceptions logged with ``exc_info`` to the current span.

    ``transform_file`` catches everything and reports a failure to ServiceX, so
    Celery never sees an exception and its instrumentation records no
    traceback. Bridging the log record onto the span puts it in Tempo without
    touching the call sites.
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
            if span.is_recording():
                span.record_exception(exc)
        except Exception:
            pass


def tracing_enabled() -> bool:
    if os.environ.get("OTEL_SDK_DISABLED", "").lower() == "true":
        return False
    return bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))


def init_tracing(service_name: str) -> bool:
    """Create the tracer provider and instrument Celery and requests.

    Must run in the process that executes the task -- the prefork child -- so
    the exporter's background thread is alive there. Returns False instead of
    raising when tracing is off or the packages are missing: no tracing backend
    should ever stop a transformer starting.
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
            "are not installed; tracing is disabled. Rebuild the sidecar image "
            "to pick up the dependencies."
        )
        return False

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": os.environ.get("INSTANCE_NAME", "servicex"),
            "service.instance.id": os.environ.get(
                "POD_NAME", os.environ.get("HOSTNAME", socket.gethostname())
            ),
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    for label, module_path, class_name in (
        ("celery", "opentelemetry.instrumentation.celery", "CeleryInstrumentor"),
        ("requests", "opentelemetry.instrumentation.requests", "RequestsInstrumentor"),
    ):
        try:
            module = __import__(module_path, fromlist=[class_name])
            getattr(module, class_name)().instrument()
        except ImportError:
            logger.warning("No OpenTelemetry instrumentation for %s installed", label)
        except Exception:
            logger.exception("Failed to instrument %s", label)

    root = logging.getLogger()
    if not any(isinstance(h, _SpanExceptionHandler) for h in root.handlers):
        root.addHandler(_SpanExceptionHandler(level=logging.ERROR))

    _initialised = True
    logger.info(
        "Tracing enabled for %s, exporting to %s",
        service_name,
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"],
    )
    return True


def flush(timeout_millis: int = 3000) -> None:
    """Push any buffered spans to the collector now.

    The BatchSpanProcessor exports on a timer, but a transformer pod is deleted
    the moment its request completes -- often within seconds of the last file
    -- and a SIGTERM'd prefork child does not reliably run the SDK's atexit
    flush. So the sidecar flushes after every task and on shutdown. Cheap: a
    task produces a handful of spans.
    """
    try:
        from opentelemetry import trace

        force_flush = getattr(trace.get_tracer_provider(), "force_flush", None)
        if force_flush:
            force_flush(timeout_millis)
    except Exception:
        logger.debug("Trace flush failed", exc_info=True)


def record_transform_failure(error_info: str, log_body: str = "", **attributes) -> None:
    """Mark the current span failed and attach the diagnosis.

    Adds a ``transform.failure`` event carrying ``error_info`` (the stats
    parser's reading of the science log), the tail of the science container's
    log, and whatever else the caller passes (file path, id, ...), then sets
    the span status to ERROR so ``{ status = error }`` finds it. A no-op when
    nothing is recording, so it is safe to call unconditionally.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.trace import Status, StatusCode
    except ImportError:
        return

    span = trace.get_current_span()
    if not span.is_recording():
        return

    event = {"servicex.error_info": error_info}
    if log_body:
        tail = log_body[-SCIENCE_LOG_TAIL_BYTES:]
        if len(tail) < len(log_body):
            tail = "[... truncated ...]\n" + tail
        event["servicex.science_log"] = tail
    for key, value in attributes.items():
        if value is not None:
            event[f"servicex.{key}"] = str(value)

    span.add_event(FAILURE_EVENT, event)
    span.set_status(Status(StatusCode.ERROR, error_info))
