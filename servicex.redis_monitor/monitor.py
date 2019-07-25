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
        sreq_id = str(req_id, 'utf-8')
        if not sreq_id.startswith('req_id:'):
            print('Foreign key. Deleting it.', sreq_id)
            r.delete(req_id)
            continue
        sreq_id = sreq_id.replace('req_id:', '')
        req_messages = r.xlen(req_id)
        req_groups = r.xinfo_groups(req_id)
        req_consumers = 0
        if req_groups:
            print('consumers:', r.xinfo_consumers(req_id, req_groups[0]["name"]))
            req_consumers = req_groups[0]["consumers"]

        print('req_id:', req_id, 'messages:', req_messages, 'rgroups:', req_groups)

        pause_it = False
        if req_messages > 99 and req_consumers == 0:
            pause_it = True

        current_usage = {
            'id': sreq_id,
            'redis_messages': req_messages,
            'redis_consumers': req_consumers,
            'pause_it': pause_it
        }
        res = requests.post(SX_HOST + '/drequest/update/', json=current_usage, verify=False)
        if res.status_code != 200:
            print('update status:', res.status_code)

        if not counter % 6:
            # delete all topics that are not found or in Done or Terminated state.
            res = requests.get(SX_HOST + '/drequest/' + sreq_id, verify=False)
            if res.status_code != 200:
                print('request status:', res.status_code)
            if res.status_code == 200:
                req = res.json()
                if req is False:
                    print('request not found. Deleting stream:', sreq_id)
                    r.delete(req_id)
                    continue
                req = req['_source']
                if req['status'] == 'Terminated' or req['status'] == 'Done':
                    print('request done. deleting stream:', sreq_id)
                    r.delete(req_id)
                    continue

    counter += 1
    time.sleep(10)
