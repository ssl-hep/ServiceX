import time
import redis
import requests

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


r = redis.Redis(host='redis.slateci.net', port=6379, db=0)
sx_host = "https://servicex.slateci.net"


counter = 0
while True:
    # TO DO
    # print('Topics:', TOPICS)
    # for topic_name in TOPICS:
    #     if topic_name.startswith('__'):
    #         continue
    #     # print('Topic name:', topic_name)
    #     current_usage = {'id': topic_name, 'kafka_lwm': 0, 'kafka_hwm': 0}
    #     tmds = TOPICS[topic_name].partitions
    #     # print(tmds)
    #     for tp in tmds:
    #         (lwm, hwm) = C.get_watermark_offsets(TopicPartition(topic_name, tp))
    #         print(lwm,hwm)
    #         current_usage['kafka_lwm'] += lwm
    #         current_usage['kafka_hwm'] += hwm

    #     print(current_usage)
    #     res = requests.post(DOMAIN + '/drequest/update/', json=current_usage, verify=False)
    #     print('update status:', res.status_code)

    #     if not counter % 100:
    #         # delete all topics that are not found or in Done or Terminated state.
    #         res = requests.get(DOMAIN + '/drequest/' + topic_name, verify=False)
    #         print('request status:', res.status_code)
    #         if res.status_code == 200:
    #             req = res.json()
    #             if req is False:
    #                 print('request not found. Deleting topic:', topic_name)
    #                 A.delete_topics([topic_name])
    #                 continue
    #             req = req['_source']
    #             if req['status'] == 'Terminated' or req['status'] == 'Done':
    #                 print('request done. deleting topic:', topic_name)
    #                 A.delete_topics([topic_name])
    #                 continue

    counter += 1
    time.sleep(10)


