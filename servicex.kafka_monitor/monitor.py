from confluent_kafka import Consumer, Producer
from confluent_kafka import KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic
import json


def stats_cb(stats_json_str):
    stats_json = json.loads(stats_json_str)
    print('STATS:', stats_json)


CONFIG = {
    'bootstrap.servers': 'servicex-kafka-1.slateci.net:19092',
    'group.id': 'monitor',
    'client.id': 'monitor',
    'session.timeout.ms': 5000,
    'stats_cb': stats_cb
}

# A = AdminClient(CONFIG)

# def create_topic(a, topic):
#     new_topics = [NewTopic(topic, num_partitions=3, replication_factor=1)]
#     fs = a.create_topics(new_topics, request_timeout=15.0)
#     for topic, f in fs.items():
#         try:
#             f.result()  # The result itself is None
#             print("Topic {} created".format(topic))
#         except KafkaException as kex:
#             ker = kex.args[0]
#             print(ker.str())
#             if ker.code() == 36:
#                 return True
#             else:
#                 return False

# create_topic(A, "example_topic")

P = Producer(CONFIG)
P.produce('mytopic', key='hello', value='world')
P.flush(30)

C = Consumer(CONFIG)

CLUS_META = C.list_topics()
print('Brokers:', CLUS_META.brokers)

TOPICS = CLUS_META.topics

print('Topics:', TOPICS)
C.subscribe(['servicex'])

try:
    while True:
        msg = C.poll(0.1)
        if msg is None:
            continue
        elif not msg.error():
            print('Received message: {0}'.format(msg.value()))
        elif msg.error().code() == KafkaError._PARTITION_EOF:
            print('End of partition reached {0}/{1}'
                  .format(msg.topic(), msg.partition()))
        else:
            print('Error occured: {0}'.format(msg.error().str()))

except KeyboardInterrupt:
    pass

finally:
    C.close()
