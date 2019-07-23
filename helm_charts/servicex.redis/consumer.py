import redis
import time
import codecs

import pyarrow as pa
import awkward

r = redis.Redis(host='redis.slateci.net', port=6379, db=0)

stream = '7HcbHGwBMWltPFRMkyC2'
group = 'my_py_group'

sInfo = None
try:
    sInfo = r.xinfo_groups(stream)
    print(sInfo)
except Exception as rex:
    print(rex)
    pass


if not sInfo:
    r.xgroup_create(stream, group, '0', mkstream=True)

# sInfo = r.xinfo_groups(stream)
# print(sInfo)

while True:
    a = r.xreadgroup(group, 'Alice', {stream: '>'}, count=1, block=None, noack=False)
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
    print('cols:', batch.num_columns, 'rows:', batch.num_rows)
    # print(batch.schema)
    # print(batch[1])
    r.xack(stream, group, mid)

    r.xdel(stream, mid)

print('consumers:', r.xinfo_consumers(stream, group))
print('pending:', r.xpending(stream, group))
# print(r.get('foo'))
