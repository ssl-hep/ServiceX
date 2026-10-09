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
from celery import Celery

from servicex_app.celery import celeryconfig
from servicex_app.celery.server_tasks import add_files_to_processing_queue
from servicex_app.celery_task_router import route_task
from servicex_app_test.test_advertised_endpoint import in_worker

REQUEST_ID = "2f748056-9db3-47f0-b51e-3ec46b8a284a"


def _request(status="Running"):
    return {
        "request_id": REQUEST_ID,
        "status": status,
        "result-destination": "object-store",
        "result-format": "parquet",
    }


@pytest.fixture
def celery_mocks(mocker):
    signature = mocker.patch("servicex_app.celery.server_tasks.current_app.signature")
    group = mocker.patch("servicex_app.celery.server_tasks.group")
    return signature, group


def test_service_endpoint_in_worker_uses_instance_name(monkeypatch, celery_mocks):
    # Celery workers run the task outside any Flask app context
    monkeypatch.setenv("INSTANCE_NAME", "rel")
    signature, group = celery_mocks

    in_worker(
        add_files_to_processing_queue,
        _request(),
        [{"id": 42, "paths": "root://a/f.root,root://b/f.root"}],
    )

    signature.assert_called_once()
    name = signature.call_args.args[0]
    kwargs = signature.call_args.kwargs["kwargs"]
    assert name == "transformer_sidecar.transform_file"
    assert kwargs == {
        "request_id": REQUEST_ID,
        "file_id": 42,
        "paths": ["root://a/f.root", "root://b/f.root"],
        "service_endpoint": "http://rel-servicex-app:8000/servicex/internal/"
        f"transformation/{REQUEST_ID}",
        "result_destination": "object-store",
        "result_format": "parquet",
    }
    group.return_value.apply_async.assert_called_once()


def test_task_does_not_recheck_request_status(monkeypatch, celery_mocks):
    # LookupResultProcessor checks the live status before enqueueing
    monkeypatch.setenv("INSTANCE_NAME", "rel")
    signature, group = celery_mocks

    in_worker(
        add_files_to_processing_queue,
        _request(status="Canceled"),
        [{"id": 1, "paths": "root://a/f.root"}],
    )

    signature.assert_called_once()
    group.return_value.apply_async.assert_called_once()


def test_celeryconfig_routes_transform_tasks():
    assert celeryconfig.task_routes == (route_task,)

    app = Celery(set_as_current=False)
    app.config_from_object("servicex_app.celery.celeryconfig")
    route = app.amqp.router.route(
        {}, "transformer_sidecar.transform_file", kwargs={"request_id": REQUEST_ID}
    )
    assert route["queue"].name == f"transformer-{REQUEST_ID}"
