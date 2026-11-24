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

from rucio_did_finder.replica_distance import ReplicaSorter

from .conftest import MINIMAL_ENV, TEST_RSE_EXPRESSION


@pytest.fixture
def import_finder(import_finder_module):
    return lambda **env: import_finder_module("rucio_did_finder.finder", **env)


class TestModuleConfiguration:
    def test_defaults(self, import_finder):
        finder = import_finder(**MINIMAL_ENV)

        assert finder.cache_prefix == ""
        assert finder.rse_expression == TEST_RSE_EXPRESSION
        assert finder.ignore_availability is False
        assert finder.location is None
        assert finder.replica_sorter is None

    def test_rucio_adapter(self, import_finder):
        finder = import_finder(**MINIMAL_ENV)

        adapter = finder.rucio_adapter
        assert adapter.did_client is finder.did_client
        assert adapter.replica_client is finder.replica_client
        assert adapter.report_logical_files is False

    def test_cache_prefix(self, import_finder):
        finder = import_finder(CACHE_PREFIX="root://cache/", **MINIMAL_ENV)
        assert finder.cache_prefix == "root://cache/"

    @pytest.mark.parametrize("missing", [{}, {"RUCIO_RSE_EXPRESSION": ""}])
    def test_rse_expression_is_required(self, import_finder, missing):
        with pytest.raises(ValueError, match="RUCIO_RSE_EXPRESSION"):
            import_finder(**missing)

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
    def test_ignore_availability(self, import_finder, value, expected):
        finder = import_finder(RUCIO_IGNORE_AVAILABILITY=value, **MINIMAL_ENV)
        assert finder.ignore_availability is expected

    def test_report_logical_files(self, import_finder):
        # if nothing in the environment, should be false
        finder = import_finder(**MINIMAL_ENV)
        assert not finder.rucio_adapter.report_logical_files
        # if set to 1 then should be true
        finder = import_finder(REPORT_LOGICAL_FILES="1", **MINIMAL_ENV)
        assert finder.rucio_adapter.report_logical_files
        # if set to something other than 1 then should be false
        finder = import_finder(REPORT_LOGICAL_FILES="", **MINIMAL_ENV)
        assert not finder.rucio_adapter.report_logical_files


class TestReplicaSorterConfiguration:
    SORTER_ENV = {
        "RUCIO_LATITUDE": "41.88",
        "RUCIO_LONGITUDE": "-88.25",
        "USE_REPLICA_SORTER": "1",
    }

    def test_enabled(self, import_finder):
        finder = import_finder(**self.SORTER_ENV, **MINIMAL_ENV)

        assert finder.location == {"latitude": 41.88, "longitude": -88.25}
        assert isinstance(finder.replica_sorter, ReplicaSorter)

    @pytest.mark.parametrize("omitted", sorted(SORTER_ENV))
    def test_disabled_unless_fully_configured(self, import_finder, omitted):
        env = {k: v for k, v in self.SORTER_ENV.items() if k != omitted}
        finder = import_finder(**env, **MINIMAL_ENV)

        assert finder.location is None
        assert finder.replica_sorter is None


class TestFindFiles:
    def test_passes_configuration_to_lookup_request(self, import_finder):
        finder = import_finder(RUCIO_IGNORE_AVAILABILITY="true", **MINIMAL_ENV)
        files = [{"paths": ["root://site/ghi"]}, {"paths": ["root://site/jkl"]}]

        with patch.object(finder, "LookupRequest") as lookup_request:
            lookup_request.return_value.lookup_files.return_value = iter(files)
            found = list(
                finder.find_files(
                    "rucio://my-did",
                    {"dataset-id": 42},
                    {"rucio_adapter": finder.rucio_adapter},
                )
            )

        assert found == files
        lookup_request.assert_called_once_with(
            did="rucio://my-did",
            rucio_adapter=finder.rucio_adapter,
            dataset_id=42,
            replica_sorter=None,
            location=None,
            rse_expression=TEST_RSE_EXPRESSION,
            ignore_availability=True,
        )

    def test_temporal_info_and_file_keys_pass_through(self, import_finder, mocker):
        """DIDFinderWorker passes the DID without its scheme and an info dict with
        extra keys; files, including their file_key, come back as the adapter made them.
        """
        finder = import_finder(**MINIMAL_ENV)
        adapter = mocker.MagicMock()
        batches = [
            [{"paths": ["root://a/f0"], "file_size": 1, "file_key": "user.x:f0"}],
            [{"paths": ["root://a/f1"], "file_size": 2, "file_key": "user.x:f1"}],
        ]
        adapter.list_files_for_did.return_value = iter(batches)
        info = {"dataset-id": 7, "did-scheme": "rucio", "did-hash": "h", "resume": None}

        found = list(finder.find_files("user.x:ds", info, {"rucio_adapter": adapter}))

        assert found == batches
        adapter.list_files_for_did.assert_called_once_with(
            "user.x:ds", rse_expression=TEST_RSE_EXPRESSION, ignore_availability=False
        )
