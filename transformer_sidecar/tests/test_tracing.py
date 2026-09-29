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
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode
from pytest import fixture

from transformer_sidecar import tracing


@fixture
def exporter():
    """A tracer that keeps its spans in memory, installed for the test only."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    span = provider.get_tracer("test").start_span("transform_file")
    # Tests end the span themselves so they can read it back from the exporter
    with trace.use_span(span, end_on_exit=False):
        yield exporter


def test_init_disabled_without_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setattr(tracing, "_initialised", False)
    assert tracing.init_tracing("servicex-transformer") is False


def test_init_respects_sdk_disabled(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setattr(tracing, "_initialised", False)
    assert tracing.init_tracing("servicex-transformer") is False


def test_record_transform_failure_marks_span(exporter):
    log = "line1\nTraceback (most recent call last):\n  boom\n"
    tracing.record_transform_failure(
        "Property naming error: pt not available",
        log,
        request_id="req-9",
        file_id="file-1",
        file_path="root://site/file.root",
        replicas_tried=2,
        object_name=None,
    )
    span = trace.get_current_span()
    span.end()

    (finished,) = exporter.get_finished_spans()
    assert finished.status.status_code == StatusCode.ERROR
    assert finished.status.description == "Property naming error: pt not available"

    (event,) = finished.events
    assert event.name == tracing.FAILURE_EVENT
    assert event.attributes["servicex.error_info"] == (
        "Property naming error: pt not available"
    )
    assert event.attributes["servicex.science_log"] == log
    assert event.attributes["servicex.request_id"] == "req-9"
    assert event.attributes["servicex.file_id"] == "file-1"
    assert event.attributes["servicex.file_path"] == "root://site/file.root"
    assert event.attributes["servicex.replicas_tried"] == "2"
    assert "servicex.object_name" not in event.attributes


def test_record_transform_failure_truncates_log(exporter):
    log = "x" * (tracing.SCIENCE_LOG_TAIL_BYTES + 100) + "END"
    tracing.record_transform_failure("too much output", log)
    span = trace.get_current_span()
    span.end()

    (finished,) = exporter.get_finished_spans()
    attached = finished.events[0].attributes["servicex.science_log"]
    assert attached.startswith("[... truncated ...]\n")
    assert attached.endswith("END")
    assert len(attached) <= tracing.SCIENCE_LOG_TAIL_BYTES + len("[... truncated ...]\n")


def test_record_transform_failure_without_span_is_noop():
    # No span is recording here; must not raise
    tracing.record_transform_failure("nothing listening")


def test_logged_exception_lands_on_span(exporter):
    logger = logging.getLogger("test_tracing")
    handler = tracing._SpanExceptionHandler(level=logging.ERROR)
    logger.addHandler(handler)
    try:
        try:
            raise ValueError("bad file")
        except ValueError:
            logger.exception("Received exception doing transform")
    finally:
        logger.removeHandler(handler)

    span = trace.get_current_span()
    span.end()

    (finished,) = exporter.get_finished_spans()
    (event,) = finished.events
    assert event.name == "exception"
    assert event.attributes["exception.type"] == "ValueError"
    assert "bad file" in event.attributes["exception.message"]
    assert "Traceback" in event.attributes["exception.stacktrace"]


def test_flush_calls_provider_force_flush(mocker):
    provider = mocker.Mock()
    mocker.patch("opentelemetry.trace.get_tracer_provider", return_value=provider)
    tracing.flush(1234)
    provider.force_flush.assert_called_once_with(1234)


def test_flush_survives_a_provider_without_force_flush(mocker):
    mocker.patch("opentelemetry.trace.get_tracer_provider", return_value=object())
    tracing.flush()
