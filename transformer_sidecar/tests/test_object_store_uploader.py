# Copyright (c) 2022, IRIS-HEP
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
import logging
from pathlib import Path
from queue import Queue
from unittest.mock import patch

import pytest

from transformer_sidecar.object_store_uploader import ObjectStoreUploader, WorkQueueItem
from transformer_sidecar.servicex_adapter import ServiceXAdapter, FileCompleteRecord

logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger().setLevel(logging.INFO)


@pytest.fixture
def servicex_adapter(mocker):
    return mocker.MagicMock(ServiceXAdapter)


@pytest.fixture
def file_complete_record(mocker):
    return FileCompleteRecord(request_id="123-456",
                              file_id=42,
                              file_path="foo/bar/test.parquet",
                              status="complete",
                              total_time=1234,
                              total_events=1234,
                              total_bytes=1234)


def test_shutdown(servicex_adapter, file_complete_record, mocker):
    with patch('transformer_sidecar.object_store_uploader.ObjectStoreManager') \
            as mock_object_store_manager:

        mock_object_store_manager.return_value = mocker.MagicMock()
        queue = Queue()
        uploader = ObjectStoreUploader(request_id="123-456", input_queue=queue,
                                       logger=logging.getLogger(),
                                       convert_root_to_parquet=False)

        # The uploader uses a multiprocessing.Process, since this operates an a separate
        # process, patching is not possible. Instead, we just call the method directly
        # with the queue filled with a file to upload and a termination signal.
        # It will run to completion.
        queue.put(WorkQueueItem(Path("/foo/bar.parquet"),
                                servicex=servicex_adapter,
                                rec=file_complete_record))
        queue.put(WorkQueueItem(None))

        # Just call the method directly
        uploader.service_work_queue()

        # If we arrive back here, we know the poison pill was processed and the
        # uploader would have shut down.
        mock_object_store_manager.assert_called_once()
        mock_object_store_manager.return_value.upload_file.assert_called_with("123-456",
                                                                              "bar.parquet",
                                                                              "/foo/bar.parquet")


@pytest.mark.skip(reason="I need better test data")
def test_convert_to_parquet(servicex_adapter, file_complete_record, mocker):
    with patch('transformer_sidecar.object_store_uploader.ObjectStoreManager') \
            as mock_object_store_manager:

        mock_object_store_manager.return_value = mocker.MagicMock()
        queue = Queue()
        uploader = ObjectStoreUploader(request_id="123-456", input_queue=queue,
                                       logger=logging.getLogger(),
                                       convert_root_to_parquet=True)
        queue.put(ObjectStoreUploader.WorkQueueItem(Path("tests/test.root"),
                                                    servicex=servicex_adapter,
                                                    rec=file_complete_record))
        queue.put(ObjectStoreUploader.WorkQueueItem(None))

        # Just call the method directly
        uploader.service_work_queue()
