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
import contextvars

import pytest
from flask import Flask

from servicex_app.advertised_endpoint import advertised_endpoint


def in_worker(fn, *args):
    """
    Run fn the way a celery worker does, with no Flask app context. A fresh
    contextvars.Context holds none, even if another test left one pushed.
    """
    return contextvars.Context().run(fn, *args)


def test_outside_app_context_uses_instance_name(monkeypatch):
    monkeypatch.setenv("INSTANCE_NAME", "rel")
    assert (
        in_worker(advertised_endpoint, "servicex/internal/transformation/1234")
        == "http://rel-servicex-app:8000/servicex/internal/transformation/1234"
    )


def test_outside_app_context_requires_instance_name(monkeypatch):
    monkeypatch.delenv("INSTANCE_NAME", raising=False)
    with pytest.raises(KeyError):
        in_worker(advertised_endpoint, "servicex")


def test_inside_app_context_uses_advertised_hostname(monkeypatch):
    monkeypatch.setenv("INSTANCE_NAME", "rel")
    app = Flask(__name__)
    app.config["ADVERTISED_HOSTNAME"] = "host.docker.internal:5000"
    with app.app_context():
        assert (
            advertised_endpoint("servicex/internal/transformation/1234")
            == "http://host.docker.internal:5000/servicex/internal/transformation/1234"
        )


def test_default_endpoint_is_the_root(monkeypatch):
    monkeypatch.setenv("INSTANCE_NAME", "rel")
    assert in_worker(advertised_endpoint) == "http://rel-servicex-app:8000/"
