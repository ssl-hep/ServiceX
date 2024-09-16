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
# -*- coding: utf-8 -*-
# pylint: disable=C0111,C0103,R0205
import random

import pika
from flask import current_app


class RabbitAdaptor(object):

    def __init__(self, amqp_url):
        """Setup the example publisher object, passing in the URL we will use
        to connect to RabbitMQ.

        :param str amqp_url: The URL for connecting to RabbitMQ

        """
        self._connection = None
        self._channel = None
        self._url_list = [pika.URLParameters(u) for u in amqp_url.split(",")]

    def connect(self):
        """This method connects to RabbitMQ, returning the connection handle.

        :rtype: pika.BlockingConnection

        """
        random.shuffle(self._url_list)
        current_app.logger.info('Connecting to %s', self._url_list)
        self._connection = pika.BlockingConnection(self._url_list)

    def open_channel(self):
        """This method will open a new channel with RabbitMQ by issuing the
        Channel.Open RPC command. When RabbitMQ confirms the channel is open
        by sending the Channel.OpenOK RPC reply, the on_channel_open method
        will be invoked.

        """
        current_app.logger.info('Creating a new channel')
        self._channel = self._connection.channel()

        # Turn on delivery confirmations
        self._channel.confirm_delivery()

        return self._connection.channel

    @property
    def channel(self):
        if not self._channel:
            if not self._connection:
                self.connect()
            self.open_channel()
        return self._channel

    def reset_closed(self):
        self._connection = None
        self._channel = None

    def setup_exchange(self, exchange_name):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command.

        :param str|unicode exchange_name: The name of the exchange to declare

        """
        current_app.logger.info('Declaring exchange %s', exchange_name)

        while True:
            try:
                channel = self.channel
                channel.exchange_declare(exchange=exchange_name)
                return
            except pika.exceptions.ConnectionClosedByBroker:
                # Uncomment this to make the example not attempt recovery
                # from server-initiated connection closure, including
                # when the node is stopped cleanly
                #
                # break
                self.reset_closed()
                continue
            # Do not recover on channel errors
            except pika.exceptions.AMQPChannelError as err:
                current_app.logger.warning("Caught a channel error: {}, retrying...".format(err))
                self.reset_closed()
                continue
            # Recover on all other connection errors
            except pika.exceptions.AMQPConnectionError:
                current_app.logger.warning("Connection was closed, retrying...")
                self.reset_closed()
                continue

    def setup_queue(self, queue_name):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command.

        :param str|unicode queue_name: The name of the queue to declare.

        """
        current_app.logger.info('Declaring queue %s', queue_name)

        while True:
            try:
                channel = self.channel
                channel.queue_declare(queue=queue_name)
                return
            except pika.exceptions.ConnectionClosedByBroker:
                current_app.logger.warning("Connection was closed by broker, stopping...")
                break
            # Attempt to reconnect if the channel closed due to timeout
            except pika.exceptions.ChannelWrongStateError:
                current_app.logger.warning("Connection was closed, retrying...")
                self.reset_closed()
                continue
            # Recover on all other connection errors
            except pika.exceptions.AMQPConnectionError:
                current_app.logger.warning("Connection was closed, retrying...")
                self.reset_closed()
                continue

    def bind_queue_to_exchange(self, exchange, queue):
        current_app.logger.info(f"Binding queue {queue} to exchange {exchange}")

        while True:
            try:
                channel = self.channel
                channel.queue_bind(exchange=exchange,
                                   queue=queue,
                                   routing_key=queue)
                return
            except pika.exceptions.ConnectionClosedByBroker:
                # Uncomment this to make the example not attempt recovery
                # from server-initiated connection closure, including
                # when the node is stopped cleanly
                #
                # break
                continue
            # Do not recover on channel errors
            except pika.exceptions.AMQPChannelError as err:
                current_app.logger.exception("Caught a channel error: {}, stopping...".format(err))
                break
            # Recover on all other connection errors
            except pika.exceptions.AMQPConnectionError:
                current_app.logger.warning("Connection was closed, retrying...")
                self.reset_closed()
                continue

    def basic_publish(self, exchange, routing_key, body):
        while True:
            try:
                channel = self.channel

                channel.basic_publish(exchange=exchange,
                                      routing_key=routing_key,
                                      body=body,
                                      properties=pika.BasicProperties(delivery_mode=1),
                                      mandatory=True)
                return

            except pika.exceptions.ConnectionClosedByBroker:
                # Uncomment this to make the example not attempt recovery
                # from server-initiated connection closure, including
                # when the node is stopped cleanly
                #
                # break
                continue
            except pika.exceptions.ChannelWrongStateError:
                current_app.logger.info("Channel in wrong state. Reset and see if that fixes it")
                self.reset_closed()
                continue

            # Do not recover on channel errors
            except pika.exceptions.AMQPChannelError as err:
                current_app.logger.exception("Caught a channel error: {}, stopping...".format(err))
                break

            # Recover on all other connection errors
            except pika.exceptions.AMQPConnectionError:
                current_app.logger.info("Connection was closed, retrying...")
                self.reset_closed()
                continue

    def close_channel(self):
        """Invoke this command to close the channel with RabbitMQ by sending
        the Channel.Close RPC command.

        """
        if self._channel is not None:
            current_app.logger.info('Closing the channel')
            self._channel.close()

    def close_connection(self):
        """This method closes the connection to RabbitMQ."""
        if self._connection is not None:
            current_app.logger.info('Closing connection')
            self._connection.close()
