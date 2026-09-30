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
from datetime import datetime
from unittest.mock import patch, PropertyMock
from freezegun import freeze_time
import pytest

from servicex_app_test.resource_test_base import ResourceTestBase


class TestFileURLGenerator(ResourceTestBase):
    @freeze_time("2026-05-13 15:57:00")
    def test_file_urls(self, mocker, client):
        "This actually doesn't need to check if the files exist"
        with patch("servicex_app.models.TransformRequest.lookup") as mock_lookup:
            with patch(
                "servicex_app.models.TransformRequest.statistics",
                new_callable=PropertyMock,
            ) as mock_stats:
                # mock_datetime_boto.now.return_value = now
                # Set up the mock to return a specific value
                fake_transform_request = self._generate_transform_request()
                fake_transform_request.submit_time = datetime(2021, 1, 1, 12, 0, 0)
                fake_transform_request.finish_time = datetime(2021, 1, 1, 12, 30, 0)
                fake_transform_request.files = 32
                fake_transform_request.files_completed = 15
                fake_transform_request.files_failed = 2

                mock_stats.return_value = {
                    "min-time": 1,
                    "max-time": 30,
                    "avg-time": 15.55,
                    "total-time": 1024,
                }

                mock_lookup.return_value = fake_transform_request
                response = client.post(
                    "/servicex/transformation/file-urls",
                    json={"request_id": 1234, "file_list": ["abc"]},
                )
            assert response.status_code == 200

            assert response.json == {
                "uris": {
                    "abc": [
                        "https://localhost:9999/1234/abc?AWSAccessKeyId=miniouser&Signature=MVA1GdmZAgIrArzgzZAdlohHZW8%3D&Expires=1810223820",  # noqa: E501
                        {},
                        1810223820,
                    ]
                }
            }

    def test_get_status_404(self, mocker, client):
        "If no transform in DB, return a 404"
        import servicex_app

        mock_transform_request_read = mocker.patch.object(
            servicex_app.models.TransformRequest, "lookup", return_value=None
        )

        response = client.post(
            "/servicex/transformation/file-urls",
            json={"request_id": 1234, "file_list": ["abc"]},
        )
        assert response.status_code == 404
        mock_transform_request_read.assert_called_with("1234")

    @pytest.mark.parametrize(
        "user_id, submitter_id, is_admin, expected_status",
        [
            (42, 42, False, 200),  # Owner asks for URLs to their own outputs
            (42, 43, True, 200),  # Admin asks for someone else's outputs
            (42, 43, False, 403),  # User asks for someone else's outputs
        ],
    )
    def test_file_urls_ownership(
        self,
        user_id,
        submitter_id,
        is_admin,
        expected_status,
        mock_jwt_extended,
        mock_requesting_user,
    ):
        fake_transform_request = self._generate_transform_request()
        fake_transform_request.submitted_by = submitter_id
        with patch(
            "servicex_app.models.TransformRequest.lookup",
            return_value=fake_transform_request,
        ):
            client = self._test_client(extra_config={"ENABLE_AUTH": True})
            with client.application.app_context():
                mock_requesting_user.id = user_id
                mock_requesting_user.admin = is_admin
                response = client.post(
                    "/servicex/transformation/file-urls",
                    json={"request_id": "BR549", "file_list": ["abc"]},
                    headers=self.fake_header(),
                )
                assert response.status_code == expected_status

    def test_internal_file_urls_open_with_auth_enabled(self):
        # The ServiceX DID finder calls the internal endpoint without any
        # credentials, so it must not apply the user ownership check.
        fake_transform_request = self._generate_transform_request()
        fake_transform_request.submitted_by = 43
        with patch(
            "servicex_app.models.TransformRequest.lookup",
            return_value=fake_transform_request,
        ):
            client = self._test_client(extra_config={"ENABLE_AUTH": True})
            response = client.post(
                "/servicex/internal/transformation/file-urls",
                json={"request_id": "BR549", "file_list": ["abc"]},
            )
        assert response.status_code == 200
        assert "abc" in response.json["uris"]
