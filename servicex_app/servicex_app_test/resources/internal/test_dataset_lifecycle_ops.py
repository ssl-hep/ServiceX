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
from datetime import datetime, timedelta, timezone

from pytest import fixture

from servicex_app.models import Dataset, db

from servicex_app_test.resource_test_base import ResourceTestBase


class TestDatasetLifecycle(ResourceTestBase):
    @fixture
    def datasets(self, client):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with client.application.app_context():
            for dataset_id, name, last_updated in [
                (1, "obsolete", now - timedelta(days=30)),
                (2, "recent", now),
                (3, "never-updated", None),
            ]:
                db.session.add(
                    Dataset(
                        last_used=now,
                        last_updated=last_updated,
                        id=dataset_id,
                        name=name,
                        events=100,
                        size=1000,
                        n_files=1,
                        lookup_status="complete",
                        did_finder="rucio",
                    )
                )
            db.session.commit()
        yield

    def test_fail_on_bad_param(self, client):
        with client.application.app_context():
            response = client.post(
                "/servicex/internal/dataset-lifecycle", json={"age": "string"}
            )
            assert response.status_code == 422

    def test_deletion(self, datasets, client):
        with client.application.app_context():
            response = client.post(
                "/servicex/internal/dataset-lifecycle", json={"age": 24}
            )
            assert response.status_code == 200
            assert response.json == {"message": "Success"}

            stale_by_name = {
                dataset.name: dataset.stale
                for dataset in db.session.query(Dataset).all()
            }
            assert stale_by_name == {
                "obsolete": True,
                "recent": False,
                "never-updated": False,
            }
