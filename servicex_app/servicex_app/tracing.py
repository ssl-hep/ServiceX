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

import os
import socket

from servicex_app.metrics import METRICS_PATH


def tracing_enabled() -> bool:
    """Whether an OTLP endpoint is configured and the SDK is not switched off."""
    if os.environ.get("OTEL_SDK_DISABLED", "").lower() == "true":
        return False
    return bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))


def init_tracing(app) -> bool:
    """Set up the tracer provider and instrument ``app`` and its libraries.

    Safe to call when tracing is switched off or the OpenTelemetry packages are
    absent: it returns ``False`` rather than raising, because a missing tracing
    backend must never stop the app from booting.

    Must be called with an application context active, and after
    ``db.init_app(app)`` -- see the SQLAlchemy note below. In production this
    runs once per gunicorn worker; a second call in the same process reuses the
    existing provider and leaves the library instrumentors alone, so only the
    first app's database engines are traced.

    :param app: the Flask application to instrument.
    :return: ``True`` if this process is now exporting spans.
    """
    if not tracing_enabled():
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        app.logger.error(
            "OTEL_EXPORTER_OTLP_ENDPOINT is set but the OpenTelemetry packages "
            "are not installed; tracing is disabled. Rebuild the servicex_app "
            "image to pick up the dependencies."
        )
        return False

    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        resource = Resource.create(
            {"service.instance.id": os.environ.get("HOSTNAME", socket.gethostname())}
        )
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)

        RequestsInstrumentor().instrument()

        from servicex_app.models import db

        SQLAlchemyInstrumentor().instrument(engines=list(db.engines.values()))

    # Per-instance rather than the class-level FlaskInstrumentor().instrument()
    FlaskInstrumentor().instrument_app(app, excluded_urls=METRICS_PATH)

    app.logger.info(
        "OpenTelemetry tracing enabled, exporting spans to %s",
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"],
    )
    return True
