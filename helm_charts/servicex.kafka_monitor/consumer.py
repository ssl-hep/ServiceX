from confluent_kafka import Consumer, Producer
from confluent_kafka import KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka import TopicPartition

TOPIC_NAME = 'test_topic4'

CONFIG = {
    'bootstrap.servers': 'servicex-kafka-0.slateci.net:19092',
    'group.id': 'ap',
    'client.id': 'ap1',
    'debug': 'broker,fetch',
    'enable.auto.commit': True,
    'session.timeout.ms': 10000
}

CCONFIG = {
    'bootstrap.servers': 'servicex-kafka-0.slateci.net:19092',
    'group.id': 'reader',
    'client.id': 'reader1',
    'debug': 'broker,fetch',
    'enable.auto.commit': True,
    'session.timeout.ms': 10000,
    'auto.offset.reset': 'earliest'
}

A = AdminClient(CONFIG)
C = Consumer(CCONFIG)
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
for i in range(123):
    P.produce(TOPIC_NAME, 'ILIJA - ' + str(i))

print('consuming some messages...')
C.subscribe([TOPIC_NAME])
for i in range(10):
    msg = C.poll()
    if msg is not None:
        print(msg.value(), msg.offset())
# C.consume(4)

TOPICS = A.list_topics().topics
print('Topics:', TOPICS)

tmds = TOPICS[TOPIC_NAME].partitions
print(tmds)

for tpi in tmds:
    tp = TopicPartition(TOPIC_NAME, tpi)
    print(tp)
    # C.subscribe([tp])
    print('lwm/hwm:', C.get_watermark_offsets(tp))
    print('topic offset:', tp.offset)
    print('commited:', C.committed([tp]))
    print('position:', C.position([tp]))
    print('position offset:', C.position([tp])[0].offset)
