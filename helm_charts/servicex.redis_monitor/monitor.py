import time
import redis
import requests

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


r = redis.Redis(host='redis.slateci.net', port=6379, db=0)
SX_HOST = "https://servicex.slateci.net"


counter = 0
while True:
    db, req_ids = r.scan()
    print('Requests:', req_ids)
    for req_id in req_ids:
        req_messages = r.xlen(req_id)
        req_groups = r.xinfo_groups(req_id)
        req_consumers = []
        if req_groups:
            req_consumers = r.xinfo_consumers(req_id, req_groups[0]["name"])
        print('req_id:', req_id, 'messages:', req_messages, 'rgroups:', req_groups, '\nrconsumers:', req_consumers)

        pause_it = False
        if req_messages > 99 and req_consumers == 0:
            pause_it = True

        current_usage = {
            'id': req_id,
            'redis_messages': req_messages,
            'redis_consumers': req_groups[0]["consumers"],
            'pause_it': pause_it
        }
        res = requests.post(SX_HOST + '/drequest/update/', json=current_usage, verify=False)
        print('update status:', res.status_code)

        if not counter % 6:
            # delete all topics that are not found or in Done or Terminated state.
            res = requests.get(SX_HOST + '/drequest/' + req_id, verify=False)
            print('request status:', res.status_code)
            if res.status_code == 200:
                req = res.json()
                if req is False:
                    print('request not found. Deleting stream:', req_id)
                    r.delete(req_id)
                    continue
                req = req['_source']
                if req['status'] == 'Terminated' or req['status'] == 'Done':
                    print('request done. deleting topic:', req_id)
                    r.delete(req_id)
                    continue

    counter += 1
    time.sleep(10)
