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
import os.path
import tempfile
import time
from pathlib import Path
from queue import Queue

from transformer_sidecar.watched_directory import WatchedDirectory
logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger().setLevel(logging.INFO)


def test_result_file_added(mocker):
    with tempfile.TemporaryDirectory() as tmpdirname:
        mock_queue = mocker.MagicMock(Queue)
        watched = WatchedDirectory(path=Path(tmpdirname),
                                   result_upload_queue=mock_queue,
                                   logger=logging,
                                   servicex=None
                                   )
        watched.start()

        with open(os.path.join(tmpdirname, "sample.txt"), "w") as sample:
            sample.write("This is a test")
            mock_queue.put.assert_not_called
            time.sleep(0.5)
            sample.write("This is more stuff")
            mock_queue.put.assert_not_called
            time.sleep(0.5)
            sample.write("This is still more stuff")
            mock_queue.put.assert_not_called

        time.sleep(3)
        mock_queue.put.assert_called
        assert mock_queue.put.call_args[0][0].endswith("sample.txt")
        assert watched.status == WatchedDirectory.TransformStatus.RUNNING


def test_job_complete(mocker):
    with tempfile.TemporaryDirectory() as tmpdirname:
        mock_queue = mocker.MagicMock(Queue)
        watched = WatchedDirectory(path=Path(tmpdirname),
                                   result_upload_queue=mock_queue,
                                   logger=logging,
                                   servicex=None
                                   )
        watched.start()
        with open(os.path.join(tmpdirname, "job.done"), "w") as done:
            done.write("All done!")
        time.sleep(1)
        assert watched.status == WatchedDirectory.TransformStatus.SUCCESS


def test_failure(mocker):
    with tempfile.TemporaryDirectory() as tmpdirname:
        mock_queue = mocker.MagicMock(Queue)
        watched = WatchedDirectory(path=Path(tmpdirname),
                                   result_upload_queue=mock_queue,
                                   logger=logging,
                                   servicex=None
                                   )
        watched.start()
        with open(os.path.join(tmpdirname, "job.log"), "w") as done:
            done.write("RunTimeError: All messed up")
        time.sleep(1)
        assert watched.status == WatchedDirectory.TransformStatus.FAILURE


def test_reported_events(mocker):
    with tempfile.TemporaryDirectory() as tmpdirname:
        mock_queue = mocker.MagicMock(Queue)
        watched = WatchedDirectory(path=Path(tmpdirname),
                                   result_upload_queue=mock_queue,
                                   logger=logging,
                                   servicex=None
                                   )
        watched.start()
        with open(os.path.join(tmpdirname, "job.log"), "w") as done:
            done.write("12 events processed out of 31 total events")
        time.sleep(1)
        assert watched.status == WatchedDirectory.TransformStatus.RUNNING
        assert watched.events == 12
        assert watched.total_events == 31


def test_log_without_events(mocker):
    with tempfile.TemporaryDirectory() as tmpdirname:
        mock_queue = mocker.MagicMock(Queue)
        watched = WatchedDirectory(path=Path(tmpdirname),
                                   result_upload_queue=mock_queue,
                                   logger=logging,
                                   servicex=None
                                   )
        watched.start()
        with open(os.path.join(tmpdirname, "job.log"), "w") as done:
            done.write("Just a random log message")
        time.sleep(1)
        assert watched.status == WatchedDirectory.TransformStatus.RUNNING
        assert watched.events == 0
        assert watched.total_events == 0
