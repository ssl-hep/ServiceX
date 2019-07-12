from confluent_kafka import Consumer, Producer
from confluent_kafka import KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka import TopicPartition
import time

TOPIC_NAME = 'test_topic6'

CONFIG = {
    'bootstrap.servers': 'servicex-kafka-0.slateci.net:19092',
    'group.id': 'producer',
    'client.id': 'ap2',
    'debug': 'broker,fetch',
    'enable.auto.commit': True,
    'session.timeout.ms': 10000
}


A = AdminClient(CONFIG)
P = Producer(CONFIG)


def create_topic(a, topic):
    new_topics = [NewTopic(topic, num_partitions=3, replication_factor=1)]
    fs = a.create_topics(new_topics, request_timeout=15.0)
    for topic, f in fs.items():
        try:
            f.result()  # The result itself is None
            print("Topic {} created".format(topic))
        except KafkaException as kex:
            ker = kex.args[0]
            print(ker.str())
            if ker.code() == 36:
                return True
            else:
                return False


print('creating topic...')
create_topic(A, TOPIC_NAME)

print('filling it up ...')
for i in range(123000):
    P.produce(TOPIC_NAME, 'ILIJA - ' + str(i))
    time.sleep(1)
