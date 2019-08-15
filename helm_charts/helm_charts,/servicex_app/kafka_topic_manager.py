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
from confluent_kafka import KafkaException
from confluent_kafka.admin import AdminClient, NewTopic

CONFIG = {
    'bootstrap.servers': 'servicex-kafka-1.slateci.net:19092',
    'group.id': 'monitor',
    'client.id': 'monitor',
    'session.timeout.ms': 5000,
}

admin = AdminClient(CONFIG)


def create_topic(topic_name, max_message_size,  num_partitions):
    config = {
        'compression.type': 'lz4',
        'max.message.bytes': max_message_size
    }

    new_topics = [NewTopic(topic_name, num_partitions=num_partitions,
                           replication_factor=1, config=config)]

    response = admin.create_topics(new_topics, request_timeout=15.0)
    for topic, res in response.items():
        try:
            res.result()   # The result itself is None
            print("Topic {} created".format(topic))
        except KafkaException as k_execpt:
            k_error = k_execpt.args[0]
            print(k_error.str())
            return k_error.code() == 36

