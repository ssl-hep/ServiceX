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
import os

import logstash

instance = os.environ.get("INSTANCE_NAME", "Unknown")


class VectorFormatter(logstash.formatter.LogstashFormatterBase):
    """
    Serializes a log record to JSON with stable, column-matching keys for the
    Vector sidecar's postgres sink (the `log_messages` table). Any non-standard
    record attributes are nested under `extra` (a JSON object). Emits bytes so
    it plugs directly into logstash.TCPLogstashHandler's newline framing.

    This mirrors VectorFormatter in servicex_app/servicex_app/__init__.py so that
    transformer rows and app rows are shaped identically; only `component`
    differs. `dataset_id` is not meaningful in a transformer and stays null.
    """

    def format(self, record):
        extra = self.get_extra_fields(record)
        message = {
            "timestamp": self.format_timestamp(record.created),
            "level": record.levelname,
            "logger": record.name,
            "instance": instance,
            "component": "transformer_sidecar",
            "message": record.getMessage(),
            "request_id": extra.pop("request_id", None),
            "extra": extra,
        }

        # If exception, add debug info
        if record.exc_info:
            message["extra"].update(self.get_debug_fields(record))

        return self.serialize(message)
