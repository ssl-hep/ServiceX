# Copyright (c) 2022, IRIS-HEP
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
# function to initialize logging
import logging
import os
import queue
from logging.handlers import QueueHandler, QueueListener

import logstash

from transformer_sidecar.transformer_logging.logstash_formatter import LogstashFormatter
from transformer_sidecar.transformer_logging.stream_formatter import StreamFormatter
from transformer_sidecar.transformer_logging.vector_formatter import VectorFormatter

instance = os.environ.get("INSTANCE_NAME", "Unknown")

# A transformer pod is created to serve a single request, so the id is a property
# of the process rather than of any one call site. transformer.init() sets this
# from --request-id as soon as the args are parsed.
request_id = None


def set_request_id(value):
    """Called once at startup, before the celery worker configures logging."""
    global request_id
    request_id = value


class RequestIdFilter(logging.Filter):
    """
    Stamp the pod's request id onto every record that doesn't already carry one.

    Call sites inside the sidecar pass extra={"request_id": ...} by hand, but
    anything logged by a library cannot: celery.*, kombu, amqp, and the stdout
    the worker redirects. Those records reach the log_messages table with a null
    request_id, which hides them from the request page's log grid.

    Records logged before set_request_id() runs keep a null request_id. That is
    only the handful emitted while this module is being imported, which happens
    before the args carrying the id have been parsed.

    This has to be attached to handlers, not to loggers. A filter on a logger
    only sees records logged directly through that logger, not the ones
    propagating up from celery's children.
    """

    def filter(self, record):
        if request_id and not getattr(record, "request_id", None):
            record.request_id = request_id
        return True


class _DirectQueueHandler(QueueHandler):
    """
    A QueueHandler that puts the record on the queue as-is.

    The stdlib's prepare() formats the record and then shallow-copies it so it
    can cross a process boundary. Our listener is a thread in this same process,
    so that buys nothing and costs a format plus a copy of every record, on the
    thread that logged it. prepare() also nulls exc_info, which is the field
    VectorFormatter checks before attaching a traceback, so skipping it is also
    what lets tracebacks reach the `extra` column at all.
    """

    def prepare(self, record):
        return record


# initialize_logging() is called more than once, and on different loggers: once
# at import against the root logger, and again from Celery's after_setup_logger
# hook against Celery's. One queue and one listener are shared across all of
# them, so repeat calls just attach another QueueHandler to the same live queue
# rather than orphaning a listener thread and its socket.
_vector_queue = None
_vector_listener = None


def initialize_logging(log=None, **kwargs):
    """
    Get a logger and initialize it so that it outputs the correct format
    :param request: Request id to insert into log messages
    :param log: optional logger to initialize
    :return: logger with correct formatting that outputs to console
    """

    logging.basicConfig(level=logging.INFO, force=True)

    if log is None:
        log = logging.getLogger()

    log.setLevel(logging.INFO)
    stream_handler = logging.StreamHandler()
    stream_formatter = StreamFormatter(
        "%(levelname)s " + f"{instance} transformer sidecar " + "%(message)s"
    )
    stream_handler.setFormatter(stream_formatter)
    stream_handler.setLevel(log.level)
    log.addHandler(stream_handler)

    logstash_host = os.environ.get("LOGSTASH_HOST")

    if logstash_host:
        logstash_port = int(os.environ.get("LOGSTASH_PORT", 5959))
        logstash_handler = logstash.TCPLogstashHandler(
            logstash_host, logstash_port, version=1
        )
        logstash_formatter = LogstashFormatter("logstash", None, None)
        logstash_handler.setFormatter(logstash_formatter)
        logstash_handler.setLevel(log.level)
        logstash_handler.addFilter(RequestIdFilter())
        log.addHandler(logstash_handler)

    _initialize_vector_logging(log)

    log.debug("Initialized logging")

    return log


def _initialize_vector_logging(log):
    """
    Ship logs to the pod's Vector sidecar over a localhost TCP socket, which
    writes them to the Postgres log_messages table. The socket send runs on a
    QueueListener background thread so logging never blocks the transform loop:
    log -> QueueHandler (unbounded queue, non-blocking put) -> listener thread ->
    TCPLogstashHandler (newline-delimited JSON) -> Vector.
    """
    global _vector_queue, _vector_listener

    vector_host = os.environ.get("VECTOR_HOST")
    vector_port = os.environ.get("VECTOR_PORT")
    if not (vector_host and vector_port):
        return

    if _vector_listener is None:
        vector_handler = logstash.TCPLogstashHandler(
            vector_host, int(vector_port), version=1
        )
        vector_handler.setFormatter(VectorFormatter("vector", None, None))
        vector_handler.setLevel(log.level)

        _vector_queue = queue.Queue(-1)
        _vector_listener = QueueListener(
            _vector_queue, vector_handler, respect_handler_level=True
        )
        _vector_listener.start()

    # basicConfig(force=True) only closes the root logger's handlers, so a
    # handler this function attached to some other logger can still be here.
    # Feeding the shared queue twice would double every record.
    if any(
        isinstance(handler, QueueHandler) and handler.queue is _vector_queue
        for handler in log.handlers
    ):
        return

    queue_handler = _DirectQueueHandler(_vector_queue)
    queue_handler.setLevel(log.level)
    # Filter here rather than on the listener's handler. Handler filters run
    # before emit(), so this stamps the record while it is still on the thread
    # that logged it, and the listener sees it already attributed.
    queue_handler.addFilter(RequestIdFilter())
    log.addHandler(queue_handler)
