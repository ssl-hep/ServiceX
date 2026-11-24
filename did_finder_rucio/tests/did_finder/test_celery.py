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

from .conftest import MINIMAL_ENV


@pytest.fixture
def import_celery(import_finder_module):
    return lambda **env: import_finder_module("rucio_did_finder.celery", **env)


class TestApp:
    def test_rucio_adapter_wired_into_app(self, import_celery):
        celery = import_celery(**MINIMAL_ENV)
        from rucio_did_finder import finder

        assert celery.app.name == "rucio"
        assert celery.app.did_finder_args["rucio_adapter"] is finder.rucio_adapter
        assert celery.find_files is finder.find_files

    def test_rse_expression_is_required(self, import_celery):
        with pytest.raises(ValueError, match="RUCIO_RSE_EXPRESSION"):
            import_celery()


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
