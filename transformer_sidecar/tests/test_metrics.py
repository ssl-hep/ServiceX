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
from prometheus_client import REGISTRY

from transformer_sidecar import metrics


def test_start_disabled_without_port(mocker, monkeypatch):
    monkeypatch.delenv("METRICS_PORT", raising=False)
    server = mocker.patch("transformer_sidecar.metrics.start_http_server")

    assert metrics.start("req-1", {"site": "s", "host": "h"}) is False
    server.assert_not_called()


def test_start_serves_and_sets_info(mocker, monkeypatch):
    monkeypatch.setenv("METRICS_PORT", "9102")
    monkeypatch.setenv("INSTANCE_NAME", "unit-test")
    monkeypatch.delenv("METRICS_ADDR", raising=False)
    server = mocker.patch("transformer_sidecar.metrics.start_http_server")

    assert metrics.start("req-2", {"site": "site-a", "host": "node-1"}) is True
    server.assert_called_once_with(9102, addr="::")

    assert (
        REGISTRY.get_sample_value(
            "servicex_transformer_info",
            {
                "request_id": "req-2",
                "instance": "unit-test",
                "site": "site-a",
                "host": "node-1",
            },
        )
        == 1
    )


def test_start_falls_back_to_ipv4(mocker, monkeypatch):
    monkeypatch.setenv("METRICS_PORT", "9102")
    server = mocker.patch(
        "transformer_sidecar.metrics.start_http_server",
        side_effect=[OSError("no ipv6"), None],
    )

    assert metrics.start("req-3", {}) is True
    assert [c.kwargs["addr"] for c in server.call_args_list] == ["::", "0.0.0.0"]


def test_record_cpu_times_skips_unknown_iowait():
    def sample(mode):
        return (
            REGISTRY.get_sample_value(
                "servicex_transformer_cpu_seconds_total", {"mode": mode}
            )
            or 0.0
        )

    before = {m: sample(m) for m in ("user", "system", "iowait")}
    metrics.record_cpu_times(user=1.5, system=0.5, iowait=-1)
    assert sample("user") - before["user"] == 1.5
    assert sample("system") - before["system"] == 0.5
    assert sample("iowait") == before["iowait"]
