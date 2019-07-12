import redis
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import awkward
import codecs

r = redis.Redis(host='localhost', port=6379, db=0)

stream = 'my_py_stream'
group = 'my_py_group'

try:
    strInfo = r.xinfo_stream(stream)
    print(strInfo)
    if strInfo:
        r.xtrim(stream, 0)
except Exception as e:
    print(e)
    pass


def pause():
    print('stream length:', r.xlen(stream))
    while r.xlen(stream) > 5000:
        time.sleep(1)


# for i in range(1000):
#     if not i % 10:
#         print("adding event:", i)
#     r.xadd(stream, {'ev': i, 'data': 'asdf - ' + str(i)})  # , maxlen=6000)
#     pause()


data = [
    pa.array([1, 2, 3, 4]),
    pa.array(['foo', 'bar', 'baz', None]),
    pa.array([True, None, False, True])
]

batch = pa.RecordBatch.from_arrays(data, ['f0', 'f1', 'f2'])

for i in range(100):
    print('adding pa ev:', i)
    sink = pa.BufferOutputStream()
    writer = pa.RecordBatchStreamWriter(sink, batch.schema)
    writer.write_batch(batch)
    r.xadd(stream, {'pa': i, 'data': codecs.encode(sink.getvalue(), 'base64')})
    pause()


# r.set('foo', 'bar')
# print(r.get('foo'))
