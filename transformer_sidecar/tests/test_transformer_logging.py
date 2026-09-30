# Copyright (c) 2026, IRIS-HEP
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

from transformer_sidecar.transformer_logging import initialize_logging


class RecordingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.closed = False

    def emit(self, record):
        pass

    def close(self):
        self.closed = True
        super().close()


def test_initialize_logging_twice(monkeypatch, capsys):
    monkeypatch.delenv("LOGSTASH_HOST", raising=False)
    log = logging.getLogger("test_initialize_logging_twice")
    log.propagate = False

    # The sidecar initializes logging at import time, and again once celery has
    # installed its own handler
    initialize_logging(log)
    first_handler = log.handlers[0]
    celery_handler = RecordingHandler()
    log.addHandler(celery_handler)

    initialize_logging(log)

    assert len(log.handlers) == 1
    assert isinstance(log.handlers[0], logging.StreamHandler)
    assert log.handlers[0] is not first_handler

    # Handlers that are dropped are closed, so a logstash socket isn't leaked
    assert celery_handler.closed

    log.info("only once")
    assert capsys.readouterr().err.count("only once") == 1
