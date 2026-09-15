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
import pytest

from servicex_did_finder_lib.exceptions import (
    NoSuchDatasetException,
    LookupFailureException,
)
import respx
import httpx


@respx.mock
def test_working_call(monkeypatch):
    monkeypatch.setenv("SERVICEX_ENDPOINT", "http://funtimes")
    from servicex_did_finder_servicex.celery import find_files

    (
        respx.get(
            "http://funtimes/servicex/transformation/4313b658-646b-4483-87be-7fa72dd5ae9c/results"
        )
        .mock()
        .respond(
            200,
            json={
                "results": [
                    {
                        "id": 3035918,
                        "request-id": "4313b658-646b-4483-87be-7fa72dd5ae9c",
                        "file-id": 3035918,
                        "file-path": "root://192.170.240.193:1094//root://ccxrootdatlas.in2p3.fr:1094//atlasdatadisk/rucio/data25_13p6TeV/00/e2/DAOD_PHYSLITE.46959278._000967.pool.root.1",  # noqa: E501
                        "s3-object-name": "root:__192.170.240.193:1094__root:__ccxrootdatlas.in2p3.fr:1094__atlasdatadisk_rucio_data25_13p6TeV_00_e2_DAOD_PHYSLITE.46959278._000967.pool.root.1",  # noqa: E501
                        "transform_status": "success",
                        "transform_time": 3,
                        "total-events": 1535,
                        "total-bytes": 79267,
                        "avg-rate": 467.1990191388671,
                        "created_at": "2026-09-15T19:37:57.205899",
                    },
                    {
                        "id": 3035919,
                        "request-id": "4313b658-646b-4483-87be-7fa72dd5ae9c",
                        "file-id": 3035919,
                        "file-path": "root://192.170.240.191:1094//root://ccxrootdatlas.in2p3.fr:1094//atlasdatadisk/rucio/data25_13p6TeV/01/31/DAOD_PHYSLITE.46959278._000664.pool.root.1",  # noqa: E501
                        "s3-object-name": "root:__192.170.240.191:1094__root:__ccxrootdatlas.in2p3.fr:1094__atlasdatadisk_rucio_data25_13p6TeV_01_31_DAOD_PHYSLITE.46959278._000664.pool.root.1",  # noqa: E501
                        "transform_status": "success",
                        "transform_time": 3,
                        "total-events": 1888,
                        "total-bytes": 96525,
                        "avg-rate": 558.0122758042185,
                        "created_at": "2026-09-15T19:37:57.316646",
                    },
                    {
                        "id": 3035920,
                        "request-id": "4313b658-646b-4483-87be-7fa72dd5ae9c",
                        "file-id": 3035920,
                        "file-path": "root://192.170.240.192:1094//root://ccxrootdatlas.in2p3.fr:1094//atlasdatadisk/rucio/data25_13p6TeV/00/6d/DAOD_PHYSLITE.46959278._000340.pool.root.1",  # noqa: E501
                        "s3-object-name": "root:__192.170.240.192:1094__root:__ccxrootdatlas.in2p3.fr:1094__atlasdatadisk_rucio_data25_13p6TeV_00_6d_DAOD_PHYSLITE.46959278._000340.pool.root.1",  # noqa: E501
                        "transform_status": "success",
                        "transform_time": 4,
                        "total-events": 2209,
                        "total-bytes": 119034,
                        "avg-rate": 546.6730422646518,
                        "created_at": "2026-09-15T19:37:57.957860",
                    },
                ]
            },
        )
    )

    respx.post(
        "http://funtimes/servicex/transformation/file-urls",
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "uris": {
                    "root:__192.170.240.193:1094__root:__ccxrootdatlas.in2p3.fr:1094__atlasdatadisk_rucio_data25_13p6TeV_00_e2_DAOD_PHYSLITE.46959278._000967.pool.root.1": [  # noqa: E501
                        "http://funtimes:32095/4313b658-646b-4483-87be-7fa72dd5ae9c/root%3A__192.170.240.193%3A1094__root%3A__ccxrootdatlas.in2p3.fr%3A1094__atlasdatadisk_rucio_data25_13p6TeV_00_e2_DAOD_PHYSLITE.46959278._000967.pool.root.1?AWSAccessKeyId=ABAOJZ4XMLKWO5H0PZJ3&Signature=5fzk7IJTpMXp5GX1OVZgOaYx%2BnU%3D&Expires=1821039798",  # noqa: E501
                        {},
                        1821039798,
                    ],
                    "root:__192.170.240.191:1094__root:__ccxrootdatlas.in2p3.fr:1094__atlasdatadisk_rucio_data25_13p6TeV_01_31_DAOD_PHYSLITE.46959278._000664.pool.root.1": [  # noqa: E501
                        "http://funtimes:32095/4313b658-646b-4483-87be-7fa72dd5ae9c/root%3A__192.170.240.191%3A1094__root%3A__ccxrootdatlas.in2p3.fr%3A1094__atlasdatadisk_rucio_data25_13p6TeV_01_31_DAOD_PHYSLITE.46959278._000664.pool.root.1?AWSAccessKeyId=ABAOJZ4XMLKWO5H0PZJ3&Signature=xMHPJ0GUBj8zGqfAPkSTwLPfTso%3D&Expires=1821039798",  # noqa: E501
                        {},
                        1821039798,
                    ],
                    "root:__192.170.240.192:1094__root:__ccxrootdatlas.in2p3.fr:1094__atlasdatadisk_rucio_data25_13p6TeV_00_6d_DAOD_PHYSLITE.46959278._000340.pool.root.1": [  # noqa: E501
                        "http://funtimes:32095/4313b658-646b-4483-87be-7fa72dd5ae9c/root%3A__192.170.240.192%3A1094__root%3A__ccxrootdatlas.in2p3.fr%3A1094__atlasdatadisk_rucio_data25_13p6TeV_00_6d_DAOD_PHYSLITE.46959278._000340.pool.root.1?AWSAccessKeyId=ABAOJZ4XMLKWO5H0PZJ3&Signature=%2F810pYM%2BzCvJnnBjuUuVWT8qYuw%3D&Expires=1821039798",  # noqa: E501
                        {},
                        1821039798,
                    ],
                }
            },
        )
    )
    iter = find_files(
        "4313b658-646b-4483-87be-7fa72dd5ae9c",
        {"dataset-id": "112233"},
    )
    files = [f for f in iter]

    assert len(files) == 3
    assert isinstance(files[0], dict)
    sorted_files = sorted(files, key=lambda x: x["paths"][0])
    assert sorted_files[0]["paths"][0] == (
        "http://funtimes:32095/4313b658-646b-4483-87be-7fa72dd5ae9c/root%3A__192.170.240.191%3A1094__root%3A__ccxrootdatlas.in2p3.fr%3A1094__atlasdatadisk_rucio_data25_13p6TeV_01_31_DAOD_PHYSLITE.46959278._000664.pool.root.1?AWSAccessKeyId=ABAOJZ4XMLKWO5H0PZJ3&Signature=xMHPJ0GUBj8zGqfAPkSTwLPfTso%3D&Expires=1821039798"  # noqa: E501
    )


@respx.mock
def test_exception_no_files(monkeypatch):
    monkeypatch.setenv("SERVICEX_ENDPOINT", "http://funtimes")
    from servicex_did_finder_servicex.celery import find_files

    (
        respx.get(
            "http://funtimes/servicex/transformation/4313b658-646b-4483-87be-7fa72dd5ae9c/results"
        )
        .mock()
        .respond(200, json={"results": []})
    )

    respx.post(
        "http://funtimes/servicex/transformation/file-urls",
    ).mock(
        return_value=httpx.Response(
            404,
            json={
                "message": "Transformation request not found with id: 4313b658-646b-4483-87be-7fa72dd5ae9c"  # noqa: E501
            },
        )
    )
    iter = find_files(
        "4313b658-646b-4483-87be-7fa72dd5ae9c",
        {"dataset-id": "112233"},
    )
    with pytest.raises(NoSuchDatasetException):
        [f for f in iter]


@respx.mock
def test_exception_io(monkeypatch):
    monkeypatch.setenv("SERVICEX_ENDPOINT", "http://funtimes")
    from servicex_did_finder_servicex.celery import find_files

    respx.get(
        "http://funtimes/servicex/transformation/4313b658-646b-4483-87be-7fa72dd5ae9c/results"
    ).mock(side_effect=httpx.ConnectError("Connection error"))
    iter = find_files(
        "4313b658-646b-4483-87be-7fa72dd5ae9c",
        {"dataset-id": "112233"},
    )
    with pytest.raises(LookupFailureException):
        [f for f in iter]
