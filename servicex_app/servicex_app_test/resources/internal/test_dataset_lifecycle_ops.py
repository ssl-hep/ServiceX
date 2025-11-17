# Copyright (c) 2025, IRIS-HEP
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
from datetime import datetime, timezone
from unittest.mock import patch

from pytest import fixture

from servicex_app.models import Dataset

from servicex_app_test.resource_test_base import ResourceTestBase


class TestDatasetLifecycle(ResourceTestBase):
    @fixture
    def fake_dataset_list(self):
        with patch(
            "servicex_app.resources.internal.dataset_lifecycle_ops.get_all_datasets"
        ) as dsfunc:
            dsfunc.return_value = [
                Dataset(
                    last_used=datetime(2022, 1, 1, tzinfo=timezone.utc),
                    last_updated=datetime(2022, 1, 1, tzinfo=timezone.utc),
                    id=1,
                    name="not-orphaned",
                    events=100,
                    size=1000,
                    n_files=1,
                    lookup_status="complete",
                    did_finder="rucio",
                ),
                Dataset(
                    last_used=datetime.now(timezone.utc),
                    last_updated=datetime.now(timezone.utc),
                    id=2,
                    name="orphaned",
                    events=100,
                    size=1000,
                    n_files=1,
                    lookup_status="complete",
                    did_finder="rucio",
                ),
            ]
            yield dsfunc

    def test_fail_on_bad_param(self, client):
        with client.application.app_context():
            response = client.post(
                "/servicex/internal/dataset-lifecycle", json={"age": "string"}
            )
            assert response.status_code == 422

    def test_deletion(self, fake_dataset_list, client):
        with client.application.app_context():
            with patch(
                "servicex_app.resources.internal.dataset_lifecycle_ops.delete_dataset"
            ) as deletion_obj:
                response = client.post(
                    "/servicex/internal/dataset-lifecycle", json={"age": 24}
                )
                fake_dataset_list.assert_called_once()
                deletion_obj.assert_called_once()
                assert response.status_code == 200
