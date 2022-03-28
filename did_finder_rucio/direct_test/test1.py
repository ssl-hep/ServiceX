"""
This test can be run standalon against actual rucio.
Simply do:
setupATLAS
lsetup rucio
voms-proxy-init
git clone https://github.com/ssl-hep/ServiceX_DID_Finder_Rucio.git
cd ServiceX_DID_Finder_Rucio
pip install -r requirements.txt
cp direct_test/test1.py src
cd src
python3 test1.py
"""
import asyncio

import logging

from rucio.client.didclient import DIDClient
from rucio.client.replicaclient import ReplicaClient
from servicex.did_finder.rucio_adapter import RucioAdapter
from servicex.did_finder.lookup_request import LookupRequest


logging.basicConfig()
logging.root.setLevel(logging.INFO)

logger = logging.getLogger("test1")
logger.info("ServiceX DID Finder starting up.")
did_client = DIDClient()
replica_client = ReplicaClient()
rucio_adapter = RucioAdapter(did_client, replica_client)


async def t1(scope, name):
    ds = scope+':'+name
    print('looking up:', ds)
    lookup_request = LookupRequest(
        did=ds,
        rucio_adapter=rucio_adapter,
        request_id='request-id'
    )

    count = 0
    for laf in lookup_request.lookup_files():
        count += 1
    print(f'found {count} files')

loop = asyncio.get_event_loop()
tasks = [
    loop.create_task(t1('dataset', 'unexisting')),
    loop.create_task(t1('data15_13TeV', 'DAOD_PHYS.21568817._001671.pool.root.1')),
    loop.create_task(
        t1(
            'user.kchoi',
            'user.kchoi.ttHML_80fb_ttZ'
        )
    ),
    loop.create_task(
        t1(
            'data15_13TeV',
            'data15_13TeV.00283429.physics_Main.deriv.DAOD_PHYS.r9264_p3083_p4165_tid21568817_00'
        )
    ),
    loop.create_task(
        t1(
            'data17_13TeV',
            'data17_13TeV.00339070.physics_Main.deriv.DAOD_PHYS.r10258_p3399_p4356_tid23589107_00'
        )
    ),
    # loop.create_task(
    #     t1(
    #         'data18_13TeV',
    #         'data18_13TeV.periodAllYear.physics_Main.PhysCont.DAOD_PHYS.grp18_v01_p4150'
    #     )
    # )
]
loop.run_until_complete(asyncio.wait(tasks))
loop.close()
