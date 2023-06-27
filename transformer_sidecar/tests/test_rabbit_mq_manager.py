# Copyright (c) 2019, IRIS-HEP
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
import socket

import pika

from transformer_sidecar.rabbit_mq_manager import RabbitMQManager
import pytest


class TestRabbitMQManager:
    @pytest.mark.skip("TODO this test does not work.")
    def test_init(self, mocker, caplog):
        def callback():
            return "hi"
        caplog.set_level(logging.INFO)
        mock_url_parameters = mocker.patch('pika.URLParameters', return_value="mock_url")
        mock_channel = mocker.MagicMock(pika.adapters.blocking_connection.BlockingChannel)
        mock_channel.basic_qos = mocker.Mock()
        mock_channel.basic_consume = mocker.Mock()
        mock_channel.start_consuming = mocker.Mock()
        mock_conn = mocker.MagicMock(pika.BlockingConnection)
        mock_conn.channel = mocker.Mock(return_value=mock_channel)

        # First attempt to connect will fail, and then after retry succeed
        mock_pika = mocker.patch('pika.BlockingConnection',
                                 side_effect=[socket.gaierror(), mock_conn])

        RabbitMQManager("http:/foo.com", "servicex", callback)

        mock_url_parameters.assert_called_with("http:/foo.com")
        mock_pika.assert_called_with("mock_url")
        mock_channel.basic_qos.assert_called_with(prefetch_count=1)

        basic_consume_config = mock_channel.basic_consume.call_args[1]
        assert basic_consume_config['queue'] == 'servicex'
        assert not basic_consume_config['auto_ack']
        mock_channel.start_consuming.assert_called()

        assert len(caplog.records) == 2
        assert caplog.records[0].levelno == logging.ERROR
        assert caplog.records[0].msg == "Failed to connect to RabbitMQ Broker.... retrying"
        assert caplog.records[1].levelno == logging.INFO
        assert caplog.records[1].msg == "Connected to RabbitMQ Broker"
