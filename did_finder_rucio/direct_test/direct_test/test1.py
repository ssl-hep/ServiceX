"""
This test can be run standalon against actual rucio.
Simply do:
setupATLAS
lsetup rucio
voms-proxy-init
python3 test1.py
"""
from rucio.client.replicaclient import ReplicaClient
from servicex.did_finder.rucio_adapter import RucioAdapter
from servicex.did_finder.lookup_request import LookupRequest

replica_client = ReplicaClient()
rucio_adapter = RucioAdapter(replica_client)

scope = 'dataset'
name = 'unexisting'
ds = scope+':'+name
lookup_request = LookupRequest(
    did=ds,
    rucio_adapter=rucio_adapter,
    request_id='request-id'
)
lookup_request.lookup_files()

scope = 'data15_13TeV'
name = 'data15_13TeV.00283429.physics_Main.deriv.DAOD_PHYS.r9264_p3083_p4165_tid21568817_00'
ds = scope+':'+name
lookup_request = LookupRequest(
    did=ds,
    rucio_adapter=rucio_adapter,
    request_id='request-id'
)
lookup_request.lookup_files()
