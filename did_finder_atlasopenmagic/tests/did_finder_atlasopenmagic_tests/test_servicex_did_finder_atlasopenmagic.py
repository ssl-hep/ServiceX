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

from did_finder_atlasopenmagic.celery import find_files
from servicex_did_finder_lib.exceptions import (
    BadDatasetNameException,
    NoSuchDatasetException,
    LookupFailureException,
)


def test_working_call():
    for did, nfiles in [("2024r-pp/700901", 11), ("2020e-13tev/data/3lep", 4)]:
        iter = find_files(did, {"request-id": "112233"})
        files = [f for f in iter]
        assert len(files) == nfiles
        assert isinstance(files[0], dict)
        assert len(files[0]["paths"]) == 1
        assert files[0]["paths"][0].startswith("root://eos")


def test_fails_on_bad_dataset_spec():
    for did in ["noslash", "too/many/slashes/here"]:
        with pytest.raises(BadDatasetNameException):
            list(find_files(did, {"request-id": "112233"}))


def test_fails_on_bad_release():
    with pytest.raises(NoSuchDatasetException):
        list(find_files("nosuchrelease/data", {"request-id": "112233"}))


def test_fails_on_bad_skim():
    with pytest.raises(NoSuchDatasetException):
        list(find_files("2024r-pp/700901/3lep", {"request-id": "112233"}))


def test_fails_on_nonexistent_dataset():
    with pytest.raises(NoSuchDatasetException):
        list(find_files("2024r-pp/notdata", {"request-id": "112233"}))


def test_bad_lookup(mocker):
    mocker.patch("atlasopenmagic.get_urls", side_effect=Exception())
    with pytest.raises(LookupFailureException):
        list(find_files("2024r-pp/700901", {"request-id": "112233"}))
