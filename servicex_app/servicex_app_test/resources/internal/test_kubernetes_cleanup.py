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
from datetime import datetime, timezone
from unittest.mock import call

from servicex_app_test.resource_test_base import ResourceTestBase
from servicex_app import TransformerManager
from kubernetes.client import models


class TestKubernetesCleanup(ResourceTestBase):
    def test_cleanup(self, mocker):
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.get_all_transformer_jobs.return_value = [
            models.V1Job(
                metadata=models.V1ObjectMeta(
                    name="abc",
                    creation_timestamp=datetime(
                        2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc
                    ),
                )
            ),
            # Next is too new, will not call
            models.V1Job(
                metadata=models.V1ObjectMeta(
                    name="jkl", creation_timestamp=datetime.now(timezone.utc)
                )
            ),
        ]
        mock_transformer_manager.get_all_transformer_configmaps.return_value = [
            models.V1ConfigMap(
                metadata=models.V1ObjectMeta(
                    name="def",
                    creation_timestamp=datetime(
                        2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc
                    ),
                )
            ),
            # Next is too new, will not call
            models.V1ConfigMap(
                metadata=models.V1ObjectMeta(
                    name="mno", creation_timestamp=datetime.now(timezone.utc)
                )
            ),
            # Next is a repeat transform ID, will not call
            models.V1ConfigMap(
                metadata=models.V1ObjectMeta(
                    name="abc",
                    creation_timestamp=datetime(
                        2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc
                    ),
                )
            ),
        ]

        client = self._test_client(
            transformation_manager=mock_transformer_manager,
            extra_config={"TRANSFORMER_MANAGER_ENABLED": True},
        )

        with client.application.app_context():
            response = client.post(
                "/servicex/internal/kubernetes-cleanup",
                json={"age": 24},
            )
            assert response.json is None

        mock_transformer_manager.get_all_transformer_jobs.assert_called_once()
        mock_transformer_manager.get_all_transformer_configmaps.assert_called_once()
        mock_transformer_manager.shutdown_transformer_job.assert_has_calls(
            [
                call("abc", "my-ws", True),
                call("def", "my-ws", True),
            ]
        )
        assert mock_transformer_manager.shutdown_transformer_job.call_count == 2

    def test_error(self, mocker):
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.get_all_transformer_jobs.return_value = [
            models.V1Job(
                metadata=models.V1ObjectMeta(
                    name="abc",
                    creation_timestamp=datetime(
                        2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc
                    ),
                )
            )
        ]
        mock_transformer_manager.shutdown_transformer_job.side_effect = Exception()

        client = self._test_client(
            transformation_manager=mock_transformer_manager,
            extra_config={"TRANSFORMER_MANAGER_ENABLED": True},
        )

        with client.application.app_context():
            response = client.post(
                "/servicex/internal/kubernetes-cleanup",
                json={"age": 24},
            )
            assert response.json is None
