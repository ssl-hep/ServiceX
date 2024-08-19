# Copyright (c) 2024, IRIS-HEP
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
import socket
from unittest.mock import MagicMock

import pytest

from transformer_sidecar.science_container_command import ScienceContainerCommand, \
    ScienceContainerException


@pytest.fixture
def mock_socket(mocker):
    mock_socket = mocker.patch('transformer_sidecar.science_container_command.socket.socket')
    mock_socket_instance = MagicMock()
    mock_socket.return_value = mock_socket_instance
    mock_socket_instance.accept.return_value = MagicMock(), MagicMock()
    return mock_socket


def test_connect(mock_socket):
    mock_socket_instance = mock_socket.return_value

    _ = ScienceContainerCommand()

    # Assert that socket was created with correct parameters
    mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)

    # Assert that bind was called with correct parameters
    mock_socket_instance.bind.assert_called_once_with(("localhost", 8081))

    # Assert that listen was called
    mock_socket_instance.listen.assert_called_once()

    # Assert that accept was called
    mock_socket_instance.accept.assert_called_once()


def test_sync(mock_socket):
    scc = ScienceContainerCommand()
    scc.conn.recv.return_value = b"GeT"
    scc.synch()
    scc.conn.recv.assert_called_once_with(4096)


def test_sync_fail(mock_socket):
    scc = ScienceContainerCommand()
    scc.conn.recv.return_value = None
    with pytest.raises(ScienceContainerException) as exc_info:
        scc.synch()

    # Verify that the exception message is as expected
    assert str(exc_info.value) == "problem in getting GeT"


def test_send(mock_socket):
    scc = ScienceContainerCommand()
    transform_request = {"foo": "bar"}
    scc.send(transform_request)
    scc.conn.send.assert_called_once_with(b'{"foo": "bar"}\n')


def test_await_response(mock_socket):
    scc = ScienceContainerCommand()
    scc.conn.recv.return_value = b"status"
    assert scc.await_response() == "status"
    scc.conn.recv.assert_called_once_with(4096)


def test_confirm(mock_socket):
    scc = ScienceContainerCommand()
    scc.confirm()
    scc.conn.send.assert_called_once_with(b"confirmed.\n")


def test_close(mock_socket):
    scc = ScienceContainerCommand()
    scc.close()
    scc.conn.close.assert_called_once()
    scc.serv.close.assert_called_once()
