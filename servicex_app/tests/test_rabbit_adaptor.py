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
import pika

from servicex.rabbit_adaptor import RabbitAdaptor
from tests.resource_test_base import ResourceTestBase


class TestRabbitAdaptor(ResourceTestBase):
    def test_connect(self, mocker, client):
        with client.application.app_context():
            mock_pika = mocker.patch('pika.BlockingConnection')
            rabbit = RabbitAdaptor("amqp://test.com")
            rabbit.connect()
            mock_pika.assert_called_with([pika.URLParameters("amqp://test.com")])

    def test_setup_queue(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.queue_declare = mocker.Mock()
            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")
            # rabbit.connect()
            rabbit.setup_queue("my_queue")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            mock_channel.queue_declare.assert_called_with(queue="my_queue")

            # Verify that second call doesn't open channel again
            mock_connection.channel.reset_mock()
            rabbit.setup_queue("my_queue")
            mock_connection.channel.assert_not_called()

    def test_setup_queue_broker_closed(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.queue_declare = mocker.Mock(
                side_effect=pika.exceptions.ConnectionClosedByBroker(1, "u-oh"))
            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")
            rabbit.setup_queue("my_queue")

    def test_setup_queue_wrong_state(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.queue_declare = mocker.Mock(
                side_effect=[
                    pika.exceptions.ChannelWrongStateError,
                    "ok"
                ]
            )
            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")
            rabbit.setup_queue("my_queue")

            mock_connection.channel.assert_called()
            assert mock_pika.call_count == 2  # Retried the connection

    def test_setup_queue_connection_error(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.queue_declare = mocker.Mock(
                side_effect=[
                    pika.exceptions.AMQPConnectionError,
                    "ok"
                ]
            )
            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")
            rabbit.setup_queue("my_queue")

            mock_connection.channel.assert_called()
            assert mock_pika.call_count == 2  # Retried the connection

    def test_bind_queue_to_exchange(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.queue_bind = mocker.Mock()
            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            rabbit.bind_queue_to_exchange("exchange1", "my_queue")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            mock_channel.queue_bind.assert_called_with(
                exchange="exchange1",
                queue="my_queue",
                routing_key='my_queue')

    def test_bind_queue_to_exchange_connection_closed(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.queue_bind = mocker.Mock()
            mock_channel.queue_bind = mocker.Mock(
                side_effect=[
                    pika.exceptions.ConnectionClosedByBroker(1, "uh-oh"),
                    "ok"
                ]
            )

            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            rabbit.bind_queue_to_exchange("exchange1", "my_queue")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            mock_channel.queue_bind.assert_called_with(
                exchange="exchange1",
                queue="my_queue",
                routing_key='my_queue')
            assert mock_channel.queue_bind.call_count == 2
            assert mock_pika.call_count == 1  # No retry

    def test_bind_queue_to_exchange_channel_error(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.queue_bind = mocker.Mock()
            mock_channel.queue_bind = mocker.Mock(
                side_effect=[
                    pika.exceptions.AMQPChannelError,
                ]
            )

            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            rabbit.bind_queue_to_exchange("exchange1", "my_queue")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            mock_channel.queue_bind.assert_called_with(
                exchange="exchange1",
                queue="my_queue",
                routing_key='my_queue')
            assert mock_channel.queue_bind.call_count == 1
            assert mock_pika.call_count == 1  # No retry

    def test_bind_queue_to_exchange_connection_error(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.queue_bind = mocker.Mock()
            mock_channel.queue_bind = mocker.Mock(
                side_effect=[
                    pika.exceptions.AMQPConnectionError,
                    "ok"
                ]
            )

            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            rabbit.bind_queue_to_exchange("exchange1", "my_queue")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            mock_channel.queue_bind.assert_called_with(
                exchange="exchange1",
                queue="my_queue",
                routing_key='my_queue')
            assert mock_channel.queue_bind.call_count == 2
            assert mock_pika.call_count == 2  # Retried the connection

    def test_basic_publish(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.basic_publish = mocker.Mock()
            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            rabbit.basic_publish("exchange1", "my_queue", "{my: body}")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            mock_channel.basic_publish.assert_called_with(
                exchange="exchange1",
                mandatory=True,
                routing_key='my_queue',
                properties=pika.BasicProperties(delivery_mode=1),
                body="{my: body}")

    def test_basic_publish_connection_closed(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.basic_publish = mocker.Mock(
                side_effect=[
                    pika.exceptions.ConnectionClosedByBroker(1, "uh-oh"),
                    "ok"
                ]
            )

            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            rabbit.basic_publish("exchange1", "my_queue", "{my: body}")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            assert mock_channel.basic_publish.call_count == 2
            assert mock_pika.call_count == 1  # No retry of connection

    def test_basic_publish_channel_error(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.basic_publish = mocker.Mock(
                side_effect=[
                    pika.exceptions.AMQPChannelError
                ]
            )

            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            rabbit.basic_publish("exchange1", "my_queue", "{my: body}")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            assert mock_channel.basic_publish.call_count == 1
            assert mock_pika.call_count == 1  # No retry of connection

    def test_basic_publish_connection_error(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.basic_publish = mocker.Mock(
                side_effect=[
                    pika.exceptions.AMQPConnectionError,
                    "ok"
                ]
            )

            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            rabbit.basic_publish("exchange1", "my_queue", "{my: body}")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            assert mock_channel.basic_publish.call_count == 2
            assert mock_pika.call_count == 2

    def test_setup_exchange(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.exchange_declare = mocker.Mock()
            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            rabbit.setup_exchange("exchange1")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            mock_channel.exchange_declare.assert_called_with(
                exchange="exchange1")

    def test_setup_exchange_connection_closed(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.exchange_declare = mocker.Mock(
                side_effect=[
                    pika.exceptions.ConnectionClosedByBroker(1, "uh-oh"),
                    "ok"
                ]
            )

            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            rabbit.setup_exchange("exchange1")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            assert mock_channel.exchange_declare.call_count == 2
            assert mock_pika.call_count == 2

    def test_setup_exchange_channel_error(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.exchange_declare = mocker.Mock(
                side_effect=[
                    pika.exceptions.AMQPChannelError,
                    "ok"
                ]
            )

            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            rabbit.setup_exchange("exchange1")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            assert mock_channel.exchange_declare.call_count == 2
            assert mock_pika.call_count == 2  # Retry on channel error

    def test_setup_exchange_connection_error(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.exchange_declare = mocker.Mock(
                side_effect=[
                    pika.exceptions.AMQPConnectionError,
                    "ok"
                ]
            )

            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            rabbit.setup_exchange("exchange1")
            mock_pika.assert_called()
            mock_connection.channel.assert_called()
            assert mock_channel.exchange_declare.call_count == 2
            assert mock_pika.call_count == 2

    def test_close_channel(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_channel = mocker.Mock()
            mock_channel.close = mocker.Mock()

            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            # If channel not open then do nothing
            rabbit.close_channel()
            mock_channel.close.assert_not_called()

            rabbit.channel
            rabbit.close_channel()
            mock_channel.close.assert_called()

    def test_close_connection(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_connection.close = mocker.Mock()

            mock_channel = mocker.Mock()

            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            # If channel not open then do nothing
            rabbit.close_connection()
            mock_connection.close.assert_not_called()

            rabbit.channel
            rabbit.close_connection()
            mock_connection.close.assert_called()

    def test_channel_acessro(self, mocker, client):
        with client.application.app_context():
            mock_connection = mocker.Mock()
            mock_connection.close = mocker.Mock()

            mock_channel = mocker.Mock()

            mock_connection.channel = mocker.Mock(return_value=mock_channel)
            mock_pika = mocker.patch('pika.BlockingConnection', return_value=mock_connection)
            mock_pika.channel = mocker.Mock()
            rabbit = RabbitAdaptor("amqp://test.com")

            assert rabbit.channel == mock_channel
            mock_pika.assert_called()
            mock_connection.channel.assert_called()

            # Test that subsequent call doesn't open a new channel
            mock_pika.reset_mock()
            mock_connection.reset_mock()
            assert rabbit.channel == mock_channel
            mock_pika.assert_not_called()
            mock_connection.assert_not_called()
