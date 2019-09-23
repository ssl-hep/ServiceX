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
from servicex.kafka_topic_manager import KafkaTopicManager


class TestKafkaTopicManager:
    def test_init(self, mocker):
        mock_kafka_admin = mocker.patch('confluent_kafka.admin.AdminClient')

        KafkaTopicManager('kafka.servicex.org:1272')
        mock_kafka_admin.assert_called()
        called_config = mock_kafka_admin.call_args[0][0]
        assert called_config['bootstrap.servers'] == 'kafka.servicex.org:1272'
        assert called_config['session.timeout.ms'] == 5000

    def test_create_topic(self, mocker):
        mock_kafka_admin = mocker.Mock()
        mocker.patch('confluent_kafka.admin.AdminClient', return_value=mock_kafka_admin)
        mock_kafka_admin.create_topics = mocker.MagicMock(return_value={
            'my=topic': mocker.Mock()
        })

        kafka_manager = KafkaTopicManager('kafka.servicex.org:1272')
        kafka_manager.create_topic('my-topic', max_message_size=1024, num_partitions=100)
        mock_kafka_admin.create_topics.assert_called()
        assert mock_kafka_admin.create_topics.call_args[1]['request_timeout'] == 15.0

        new_topic_request = mock_kafka_admin.create_topics.call_args[0][0][0]
        assert new_topic_request.topic == 'my-topic'
        assert new_topic_request.num_partitions == 100
        assert new_topic_request.replication_factor == 1

        assert new_topic_request.config['compression.type'] == 'lz4'
        assert new_topic_request.config['max.message.bytes'] == 1024

    def test_create_topic_exception(self, mocker):
        mock_kafka_admin = mocker.Mock()
        mocker.patch('confluent_kafka.admin.AdminClient', return_value=mock_kafka_admin)
        from confluent_kafka.cimpl import KafkaException
        mock_kafka_admin.create_topics = mocker.MagicMock(side_effect=KafkaException('fo'))

        kafka_manager = KafkaTopicManager('kafka.servicex.org:1272')

        result = kafka_manager.create_topic('my-topic', max_message_size=1024, num_partitions=100)
        assert not result
