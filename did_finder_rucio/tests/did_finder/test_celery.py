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
import importlib
import os
import sys
from unittest.mock import patch

import pytest

from rucio_did_finder.replica_distance import ReplicaSorter

MODULE_NAME = "rucio_did_finder.celery"

TEST_RSE_EXPRESSION = "cloud=CERN"
MINIMAL_ENV = {"RUCIO_RSE_EXPRESSION": TEST_RSE_EXPRESSION}


@pytest.fixture
def import_celery():
    """Import the celery module under a controlled environment.

    The module does all of its configuration at import time and builds live
    Rucio clients, so it is imported afresh for each test with those clients
    patched out and `os.environ` replaced by exactly what the test asks for.
    """

    def _import(**env):
        sys.modules.pop(MODULE_NAME, None)
        with patch("rucio.client.didclient.DIDClient"), patch(
            "rucio.client.replicaclient.ReplicaClient"
        ), patch.dict(os.environ, env, clear=True):
            return importlib.import_module(MODULE_NAME)

    yield _import
    # Don't leave a module built from a synthetic environment behind for
    # anything else that imports it.
    sys.modules.pop(MODULE_NAME, None)


class TestModuleConfiguration:
    def test_defaults(self, import_celery):
        celery = import_celery(**MINIMAL_ENV)

        assert celery.cache_prefix == ""
        assert celery.rse_expression == TEST_RSE_EXPRESSION
        assert celery.ignore_availability is False
        assert celery.location is None
        assert celery.replica_sorter is None

    def test_rucio_adapter_wired_into_app(self, import_celery):
        celery = import_celery(**MINIMAL_ENV)

        adapter = celery.app.did_finder_args["rucio_adapter"]
        assert adapter is celery.rucio_adapter
        assert adapter.did_client is celery.did_client
        assert adapter.replica_client is celery.replica_client
        assert adapter.report_logical_files is False
        assert celery.app.name == "rucio"

    def test_cache_prefix(self, import_celery):
        celery = import_celery(CACHE_PREFIX="root://cache/", **MINIMAL_ENV)
        assert celery.cache_prefix == "root://cache/"

    @pytest.mark.parametrize("missing", [{}, {"RUCIO_RSE_EXPRESSION": ""}])
    def test_rse_expression_is_required(self, import_celery, missing):
        with pytest.raises(ValueError, match="RUCIO_RSE_EXPRESSION"):
            import_celery(**missing)

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("true", True),
            ("True", True),
            ("1", True),
            ("yes", True),
            ("YES", True),
            ("false", False),
            ("no", False),
            ("", False),
        ],
    )
    def test_ignore_availability(self, import_celery, value, expected):
        celery = import_celery(RUCIO_IGNORE_AVAILABILITY=value, **MINIMAL_ENV)
        assert celery.ignore_availability is expected


class TestReplicaSorterConfiguration:
    SORTER_ENV = {
        "RUCIO_LATITUDE": "41.88",
        "RUCIO_LONGITUDE": "-88.25",
        "USE_REPLICA_SORTER": "1",
    }

    def test_enabled(self, import_celery):
        celery = import_celery(**self.SORTER_ENV, **MINIMAL_ENV)

        assert celery.location == {"latitude": 41.88, "longitude": -88.25}
        assert isinstance(celery.replica_sorter, ReplicaSorter)

    @pytest.mark.parametrize("omitted", sorted(SORTER_ENV))
    def test_disabled_unless_fully_configured(self, import_celery, omitted):
        env = {k: v for k, v in self.SORTER_ENV.items() if k != omitted}
        celery = import_celery(**env, **MINIMAL_ENV)

        assert celery.location is None
        assert celery.replica_sorter is None


class TestFindFiles:
    def test_passes_configuration_to_lookup_request(self, import_celery):
        celery = import_celery(RUCIO_IGNORE_AVAILABILITY="true", **MINIMAL_ENV)
        files = [{"paths": ["root://site/ghi"]}, {"paths": ["root://site/jkl"]}]

        with patch.object(celery, "LookupRequest") as lookup_request:
            lookup_request.return_value.lookup_files.return_value = iter(files)
            found = list(
                celery.find_files(
                    "rucio://my-did",
                    {"dataset-id": 42},
                    celery.app.did_finder_args,
                )
            )

        assert found == files
        lookup_request.assert_called_once_with(
            did="rucio://my-did",
            rucio_adapter=celery.rucio_adapter,
            dataset_id=42,
            replica_sorter=None,
            location=None,
            rse_expression=TEST_RSE_EXPRESSION,
            ignore_availability=True,
        )


class TestLookupDatasetTask:
    def test_delegates_to_do_lookup(self, import_celery):
        celery = import_celery(**MINIMAL_ENV)

        with patch(
            "servicex_did_finder_lib.did_finder_app.DIDFinderTask.do_lookup"
        ) as do_lookup:
            celery.lookup_dataset(
                did="rucio://my-did", dataset_id=42, endpoint="http://servicex"
            )

        do_lookup.assert_called_once_with(
            did="rucio://my-did",
            dataset_id=42,
            endpoint="http://servicex",
            user_did_finder=celery.find_files,
        )
