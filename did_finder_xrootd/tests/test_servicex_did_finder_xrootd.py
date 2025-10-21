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
import pytest
from servicex_did_finder_xrootd.celery import find_files
from servicex_did_finder_lib.exceptions import (
    NoSuchDatasetException,
    LookupFailureException,
)


def test_working_call():
    iter = find_files(
        (
            "root://eospublic.cern.ch//eos/opendata/atlas/"
            "OutreachDatasets/2020-01-22/4lep/MC/*"
        ),
        {"dataset-id": "112233"},
    )
    files = [f for f in iter]

    assert len(files) == 106
    assert isinstance(files[0], dict)
    sorted_files = sorted(files, key=lambda x: x["paths"][0])
    assert sorted_files[0]["paths"][0] == (
        "root://eospublic.cern.ch//eos/opendata/atlas/"
        "OutreachDatasets/2020-01-22/4lep/MC/mc_301215.ZPrime2000_ee.4lep.root"
    )


def test_exception_no_files():
    iter = find_files(
        (
            "root://eospublic.cern.ch//eos/opendata/atlas/"
            "OutreachDatasets/2020-01-22/4lep/MC/dummy*"
        ),
        {"dataset-id": "112233"},
    )
    with pytest.raises(NoSuchDatasetException):
        [f for f in iter]


def test_exception_io(mocker):
    mocker.patch("XRootD.client.glob", side_effect=Exception)
    iter = find_files(
        (
            "root://eospublic.cern.ch//eos/opendata/atlas/"
            "OutreachDatasets/2020-01-22/4lep/MC/dummy*"
        ),
        {"dataset-id": "112233"},
    )
    with pytest.raises(LookupFailureException):
        [f for f in iter]
