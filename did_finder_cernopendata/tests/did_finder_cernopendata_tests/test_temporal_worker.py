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
from unittest.mock import patch

import pytest
from servicex_did_finder_lib import DIDFinderWorker

HELM_ENDPOINT = "http://sx-servicex-app:8000/servicex/internal/transformation/"


def test_main_runs_worker_for_cernopendata():
    from did_finder_cernopendata import finder, temporal_worker

    with patch.object(temporal_worker, "DIDFinderWorker") as worker_cls:
        temporal_worker.main()

    worker_cls.assert_called_once_with("cernopendata", finder.find_files)
    worker_cls.return_value.run.assert_called_once_with()


def test_worker_settings_from_helm_env(monkeypatch):
    """Build the real worker from the env the Helm chart sets, without connecting
    to Temporal."""
    from did_finder_cernopendata import finder, temporal_worker

    monkeypatch.delenv("TEMPORAL_TASK_QUEUE", raising=False)
    monkeypatch.setenv("TEMPORAL_ADDRESS", "sx-temporal-frontend:7233")
    monkeypatch.setenv("TEMPORAL_NAMESPACE", "servicex")
    monkeypatch.setenv("SERVICEX_INTERNAL_ENDPOINT", HELM_ENDPOINT)
    monkeypatch.setenv("DID_FINDER_MAX_CONCURRENT", "1")
    built = []
    with patch.object(DIDFinderWorker, "run", lambda self: built.append(self)):
        temporal_worker.main()

    (worker,) = built
    assert worker.name == "cernopendata"
    assert worker.task_queue == "did-finder-cernopendata"
    assert worker.temporal_address == "sx-temporal-frontend:7233"
    assert worker.temporal_namespace == "servicex"
    assert worker.max_concurrent_lookups == 1
    assert worker.servicex_endpoint == HELM_ENDPOINT
    assert worker.activity.user_did_finder is finder.find_files
    assert worker.activity.did_finder_args is None


def test_requires_servicex_internal_endpoint(monkeypatch):
    from did_finder_cernopendata import temporal_worker

    monkeypatch.delenv("SERVICEX_INTERNAL_ENDPOINT", raising=False)
    with pytest.raises(ValueError, match="SERVICEX_INTERNAL_ENDPOINT"):
        temporal_worker.main()
