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
from unittest.mock import patch

import pytest
from servicex_did_finder_lib import DIDFinderWorker

from .conftest import MINIMAL_ENV


@pytest.fixture
def import_temporal_worker(import_finder_module):
    return lambda **env: import_finder_module("rucio_did_finder.temporal_worker", **env)


class TestTemporalEntrypoint:
    def test_main_runs_worker_for_rucio(self, import_temporal_worker):
        temporal_worker = import_temporal_worker(**MINIMAL_ENV)
        from rucio_did_finder import finder

        with patch.object(temporal_worker, "DIDFinderWorker") as worker_cls:
            temporal_worker.main()

        worker_cls.assert_called_once_with(
            "rucio",
            finder.find_files,
            did_finder_args={"rucio_adapter": finder.rucio_adapter},
        )
        worker_cls.return_value.run.assert_called_once_with()

    def test_worker_settings_from_helm_env(self, import_temporal_worker, monkeypatch):
        """Build the real worker from the env the Helm chart sets, without
        connecting to Temporal."""
        temporal_worker = import_temporal_worker(**MINIMAL_ENV)
        from rucio_did_finder import finder

        monkeypatch.delenv("TEMPORAL_TASK_QUEUE", raising=False)
        monkeypatch.setenv("TEMPORAL_ADDRESS", "sx-temporal-frontend:7233")
        monkeypatch.setenv("TEMPORAL_NAMESPACE", "servicex")
        monkeypatch.setenv(
            "SERVICEX_INTERNAL_ENDPOINT",
            "http://sx-servicex-app:8000/servicex/internal/transformation/",
        )
        monkeypatch.setenv("DID_FINDER_MAX_CONCURRENT", "5")
        built = []
        with patch.object(DIDFinderWorker, "run", lambda self: built.append(self)):
            temporal_worker.main()

        (worker,) = built
        assert worker.name == "rucio"
        assert worker.task_queue == "did-finder-rucio"
        assert worker.temporal_address == "sx-temporal-frontend:7233"
        assert worker.temporal_namespace == "servicex"
        assert worker.max_concurrent_lookups == 5
        assert worker.servicex_endpoint == (
            "http://sx-servicex-app:8000/servicex/internal/transformation/"
        )
        assert worker.activity.user_did_finder is finder.find_files
        assert worker.activity.did_finder_args == {
            "rucio_adapter": finder.rucio_adapter
        }
