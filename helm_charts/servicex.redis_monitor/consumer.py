import os
import time
import codecs
import redis

import pyarrow as pa
# import awkward
import requests

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


r = redis.Redis(host='redis.slateci.net', port=6379, db=0)
SX_HOST = "https://servicex.slateci.net"
SREQ_ID = "Kso2KmwBMWltPFRMMgVl"
GROUP = "ilijas_group"

if 'REQ_ID' in os.environ:
    SREQ_ID = os.environ['REQ_ID']

if 'GROUP' in os.environ:
    GROUP = os.environ['GROUP']


# check if stream is there
req_id = 'req_id:' + SREQ_ID
print('looking for stream:', req_id)
found = False
while not found:
    _db, streams = r.scan()
    print(streams)
    for s in streams:
        if req_id == str(s, 'utf-8'):
            found = True
    time.sleep(5)

sGroup = None
try:
    sGroup = r.xinfo_groups(req_id)
    print('stream group info:', sGroup[0])
except Exception as rex:
    print("stream group not there: ", rex)

if not sGroup:
    print("creating stream group")
    r.xgroup_create(req_id, GROUP, '0', mkstream=True)

# sInfo = r.xinfo_groups(req_id)
# print(sInfo)
print('start fetching data...')
tot_processed = 0
while True:
    a = r.xreadgroup(GROUP, 'Alice', {req_id: '>'}, count=1, block=None, noack=False)
    if not a:
        # print("Done.")
        time.sleep(.5)
        # break
        continue

    # print(a[0][1][0])
    mid = a[0][1][0][0]
    # print(mid)
    mess = a[0][1][0][1]
    # print(mess)
    evid = a[0][1][0][1][b'pa']
    data = a[0][1][0][1][b'data']
    print(evid)
    # print(data)
    adata = codecs.decode(data, 'bz2')

    reader = pa.ipc.open_stream(adata)
    batches = [b for b in reader]
    batch = batches[0]
    # print(batch.schema)
    # print(batch[1])
    requests.put(SX_HOST + "/drequest/events_processed/" + SREQ_ID + "/" + str(batch.num_rows), verify=False)
    tot_processed += batch.num_rows
    print('cols:', batch.num_columns, 'rows:', batch.num_rows, 'processed:', tot_processed)
    r.xack(req_id, GROUP, mid)
    r.xdel(req_id, mid)

print('consumers:', r.xinfo_consumers(req_id, GROUP))
print('pending:', r.xpending(req_id, GROUP))
# print(r.get('foo'))
