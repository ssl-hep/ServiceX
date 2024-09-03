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
import threading

from time import sleep
import logging

import pika
import socket


class RabbitMQManager(threading.Thread):
    """
    Class to manage the connection to RabbitMQ and to service the queue.
    Instances of this class run in their own thread
    """

    def __init__(self, rabbit_uri, queue_name, callback):

        handler = logging.NullHandler()
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(handler)
        self.queue_name = queue_name
        self.callback = callback

        self.rabbitmq = pika.BlockingConnection(
            pika.URLParameters(rabbit_uri)
        )

        super().__init__(target=self.connect_and_service, daemon=True)

    def connect_and_service(self):
        while True:
            try:
                _channel = self.rabbitmq.channel()

                # Set to one since our ops take a long time.
                # Give another client a chance
                _channel.basic_qos(prefetch_count=1)

                _channel.basic_consume(queue=self.queue_name,
                                       auto_ack=False,
                                       on_message_callback=self.callback)
                _channel.start_consuming()
            except socket.gaierror:
                self.logger.error("Failed to connect to RabbitMQ Broker.... retrying")
                sleep(10)