"""
This test can be run standalon against actual rucio.
Simply do:
setupATLAS
lsetup rucio
voms-proxy-init
pip install -r requirements.txt
python3 direct_test/test1.py
"""
import asyncio

from rucio.client.replicaclient import ReplicaClient
from servicex.did_finder.rucio_adapter import RucioAdapter
from servicex.did_finder.lookup_request import LookupRequest

replica_client = ReplicaClient()
rucio_adapter = RucioAdapter(replica_client)


async def t1(scope, name):
    ds = scope+':'+name
    lookup_request = LookupRequest(
        did=ds,
        rucio_adapter=rucio_adapter,
        request_id='request-id'
    )
    all_files = await lookup_request.lookup_files()
    print('looking up:', ds)
    for af in all_files:
        print(af)

loop = asyncio.get_event_loop()
tasks = [
    loop.create_task(t1('dataset', 'unexisting')),
    loop.create_task(
        t1(
            'data15_13TeV',
            'data15_13TeV.00283429.physics_Main.deriv.DAOD_PHYS.r9264_p3083_p4165_tid21568817_00'
        )
    )
]
loop.run_until_complete(asyncio.wait(tasks))
loop.close()
