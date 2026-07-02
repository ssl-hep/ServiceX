# Copyright (c) 2019-25, IRIS-HEP
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
import os

import logstash
import functools

instance = os.environ.get("INSTANCE_NAME", "Unknown")


class LogstashFormatter(logstash.formatter.LogstashFormatterBase):
    def __init__(self, component_name=None, message_type='Logstash', tags=None, fqdn=False):
        super().__init__(message_type, tags, fqdn)
        self.component_name = component_name


    def format(self, record):
        message = {
            "@timestamp": self.format_timestamp(record.created),
            "@version": "1",
            "message": record.getMessage(),
            "path": record.pathname,
            "tags": self.tags,
            "type": self.message_type,
            "instance": instance,
            "component": self.component_name,
            # Extra Fields
            "level": record.levelname,
        }

        # Add extra fields
        message.update(self.get_extra_fields(record))

        # If exception, add debug info
        if record.exc_info:
            message.update(self.get_debug_fields(record))

        return self.serialize(message)


class StreamFormatter(logging.Formatter):
    """
    A custom formatter that adds extras.
    Normally log messages are "level instance component msg extra: {}"
    """

    def_keys = [
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
    ]

    def format(self, record: logging.LogRecord) -> str:
        """
        :param record: LogRecord
        :return: formatted log message
        """

        string = super().format(record)
        extra = {k: v for k, v in record.__dict__.items() if k not in self.def_keys}
        if len(extra) > 0:
            string += " extra: " + str(extra)
        return string


@functools.lru_cache
def initialize_logging(log=None, **kwargs):
    """
    Get a logger and initialize it so that it outputs the correct format
    :param request: Request id to insert into log messages
    :param log: optional logger to initialize
    :return: logger with correct formatting that outputs to console
    """

    if log is None:
        log = logging.getLogger("rucio_did_finder")

    log.setLevel(logging.INFO)
    log.propagate = False  # keep our records out of the root logger Celery hijacks

    stream_handler = logging.StreamHandler()
    stream_formatter = StreamFormatter(
        "%(levelname)s " + f"{instance} rucio_did_finder " + "%(message)s"
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
        logstash_formatter = LogstashFormatter(component_name="rucio_did_finder")
        logstash_handler.setFormatter(logstash_formatter)
        logstash_handler.setLevel(log.level)
        log.addHandler(logstash_handler)

    log.info("Initialized logging")

    return log
