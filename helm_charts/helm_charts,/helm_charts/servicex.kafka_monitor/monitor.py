import time
import requests

from confluent_kafka import Consumer
from confluent_kafka import KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka import TopicPartition
# import json

DOMAIN = 'https://servicex.slateci.net'
TOPIC_NAME = 'mytopic'


# def stats_cb(stats_json_str):
#     stats_json = json.loads(stats_json_str)
#     print('STATS:', stats_json)


CONFIG = {
    'bootstrap.servers': 'servicex-kafka-0.slateci.net:19092,servicex-kafka-1.slateci.net:19092',
    'group.id': 'monitor',
    'client.id': 'monitor',
    'session.timeout.ms': 5000,
    # 'stats_cb': stats_cb
}

A = AdminClient(CONFIG)

counter = 0
while True:

    CLUS_META = A.list_topics()
    # print('Brokers:', CLUS_META.brokers)
    TOPICS = CLUS_META.topics
    # print('Topics:', TOPICS)

    C = Consumer(CONFIG)

    for topic_name in TOPICS:
        if topic_name.startswith('__'):
            continue
        # print('Topic name:', topic_name)
        current_usage = {'id': topic_name, 'kafka_lwm': 0, 'kafka_hwm': 0}
        tmds = TOPICS[topic_name].partitions
        # print(tmds)
        for tp in tmds:
            (lwm, hwm) = C.get_watermark_offsets(TopicPartition(topic_name, tp))
            current_usage['kafka_lwm'] += lwm
            current_usage['kafka_hwm'] += hwm

        print(current_usage)
        res = requests.post(DOMAIN + '/drequest/update/', json=current_usage, verify=False)
        print('update status:', res.status_code)

        if not counter % 100:
            # delete all topics that are not found or in Done or Terminated state.
            res = requests.get(DOMAIN + '/drequest/' + topic_name, verify=False)
            print('request status:', res.status_code)
            if res.status_code == 200:
                req = res.json()
                if req == False:
                    print('request not found. Deleting topic:', topic_name)
                    A.delete_topics([topic_name])
                    continue
                req = req['_source']
                if req['status'] == 'Terminated' or req['status'] == 'Done':
                    print('request done. deleting topic:', topic_name)
                    A.delete_topics([topic_name])
                    continue

    counter += 1
    time.sleep(10)


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
# create_topic(A, TOPIC_NAME)
