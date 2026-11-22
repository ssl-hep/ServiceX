#  Copyright (c) 2021 , IRIS-HEP
#   All rights reserved.
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice, this
#     list of conditions and the following disclaimer.
#
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#
#   * Neither the name of the copyright holder nor the names of its
#     contributors may be used to endorse or promote products derived from
#     this software without specific prior written permission.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#   DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#   FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#   DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#   SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#   CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#   OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#   OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from temporalio.common import WorkflowIDConflictPolicy

from servicex_app.temporal_adaptor import TemporalAdaptor


@pytest.fixture
def request_rec():
    return SimpleNamespace(
        request_id="1234",
        did="rucio://mc23:some.dataset",
        did_id=42,
        image="sslhep/servicex_func_adl_xaod_transformer:develop",
        generated_code_cm="my-cm",
        transformer_language="python",
        transformer_command="transform_single_file.py",
        result_destination="object-store",
        result_format="parquet",
    )


@pytest.fixture
def mock_connect(mocker):
    client = MagicMock()
    client.start_workflow = AsyncMock(
        return_value=SimpleNamespace(result_run_id="run-1")
    )
    return mocker.patch(
        "servicex_app.temporal_adaptor.Client.connect",
        new=AsyncMock(return_value=client),
    )


def test_no_connection_until_first_use(mock_connect):
    TemporalAdaptor("temporal:7233", "servicex", "servicex-orchestrator")
    mock_connect.assert_not_called()


def test_start_transform_request(mock_connect, request_rec):
    adaptor = TemporalAdaptor("temporal:7233", "servicex", "servicex-orchestrator")

    run_id = adaptor.start_transform_request(request_rec, "rucio", 20)

    assert run_id == "run-1"
    mock_connect.assert_awaited_once_with("temporal:7233", namespace="servicex")
    client = mock_connect.return_value
    client.start_workflow.assert_awaited_once_with(
        "TransformRequestWorkflow",
        {
            "request_id": "1234",
            "did": "rucio://mc23:some.dataset",
            "did_scheme": "rucio",
            "dataset_id": 42,
            "image": "sslhep/servicex_func_adl_xaod_transformer:develop",
            "generated_code_cm": "my-cm",
            "transformer_language": "python",
            "transformer_command": "transform_single_file.py",
            "result_destination": "object-store",
            "result_format": "parquet",
            "max_workers": 20,
        },
        id="transform-1234",
        task_queue="servicex-orchestrator",
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


def test_reuses_connection(mock_connect, request_rec):
    adaptor = TemporalAdaptor("temporal:7233", "servicex", "servicex-orchestrator")
    adaptor.start_transform_request(request_rec, "rucio", 20)
    adaptor.start_transform_request(request_rec, "rucio", 20)
    assert mock_connect.await_count == 1
    assert mock_connect.return_value.start_workflow.await_count == 2


def test_connection_error_propagates(mocker, request_rec):
    mocker.patch(
        "servicex_app.temporal_adaptor.Client.connect",
        new=AsyncMock(side_effect=RuntimeError("unreachable")),
    )
    adaptor = TemporalAdaptor("temporal:7233", "servicex", "servicex-orchestrator")
    with pytest.raises(RuntimeError, match="unreachable"):
        adaptor.start_transform_request(request_rec, "rucio", 20)
