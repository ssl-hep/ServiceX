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
import time
import os
from pathlib import Path
from queue import Queue
import pytest
from transformer_sidecar.object_store_manager import ObjectStoreManager


from transformer_sidecar.object_store_uploader import ObjectStoreUploader
logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger().setLevel(logging.INFO)


@pytest.fixture
def object_store_manager(mocker):
    return mocker.MagicMock(ObjectStoreManager)


def test_shutdown(object_store_manager):
    queue = Queue()
    uploader = ObjectStoreUploader(request_id="123-456", input_queue=queue,
                                   object_store=object_store_manager,
                                   logger=logging.getLogger(),
                                   convert_root_to_parquet=False)
    uploader.start()
    queue.put(ObjectStoreUploader.WorkQueueItem(Path("/foo/bar")))
    queue.put(ObjectStoreUploader.WorkQueueItem(None))
    time.sleep(1)


def test_upload(object_store_manager):
    queue = Queue()
    uploader = ObjectStoreUploader(request_id="123-456", input_queue=queue,
                                   object_store=object_store_manager,
                                   logger=logging.getLogger(),
                                   convert_root_to_parquet=False)
    uploader.start()
    pth = os.path.join("foo", "bar", "test.parquet")
    queue.put(ObjectStoreUploader.WorkQueueItem(Path(pth)))
    queue.put(ObjectStoreUploader.WorkQueueItem(None))
    time.sleep(1)
    object_store_manager.upload_file.assert_called_with("123-456",
                                                        "test.parquet",
                                                        pth)
