import time
from datetime import datetime
import json
from rucio.client import ReplicaClient
from rucio.client import DIDClient
from rucio.common import exception as rucioe
import requests

with open('config/config.json') as json_file:
    conf = json.load(json_file)

print('configuration:\n', conf)

print('sleeping until CAs are there...')

time.sleep(60)

# es = Elasticsearch([conf['ES_HOST']], timeout=60)


while True:
    RES = requests.get('https://' + conf['SITENAME'] + '/drequest/status/Defined', verify=False)
    REQ = RES.json()
    if REQ is None:
        time.sleep(10)
        continue

    print("processing request:\n", REQ)

    UPDATE_STATUS = requests.put('https://' + conf['SITENAME'] + '/drequest/status/' + REQ['_id'] + '/' + 'Defining', verify=False)
    print('UPDATE_STATUS:', UPDATE_STATUS)
    if UPDATE_STATUS.status_code != 200:
        continue

    try:
        rc = ReplicaClient()
        dc = DIDClient()
    except e:
        print('problem in getting rucio client', e)
        break

    doc = REQ["_source"]
    ds = doc['dataset']
    (scope, name) = ds.split(":")
    try:
        g_files = dc.list_files(scope, name)
    except rucioe.DataIdentifierNotFound as didnf:
        print('could not find data set. Setting request to failed.', didnf)
        g_files = []
    except re.CannotAuthenticate as ca:
        print('cant authenticate', ca)
    except Exception as e:
        print('Unexpected error. Will retry. ', e)

    files = []
    files_skipped = 0
    dataset_size = 0
    dataset_events = 0

    for f in g_files:
        print(f)
        f_scope = f['scope']
        f_name = f['name']
        dataset_size += f['bytes']
        dataset_events += f['events']
        try:
            g_replicas = rc.list_replicas(
                dids=[{'scope': f_scope, 'name': f_name}],
                schemes=['root'],
                client_location={'site': conf['SITE']})
        except Exception as e:
            print('could not find file replica. Skipping file:', f_name, e)
            files_skipped += 1
            continue

        for r in g_replicas:
            # print(r)
            sel_path = ''
            if 'pfns' not in r:
                continue
            for fpath, meta in r['pfns'].iteritems():
                if not meta['type'] == 'DISK':
                    continue
                sel_path = fpath
                if meta['domain'] == 'lan':
                    break
            if sel_path == '':
                files_skipped += 1
                continue
            files.append({
                "_index": "servicex_paths",
                "_type": "docs",
                "_source": {
                    'req_id': hit["_id"],
                    'adler32': f['adler32'],
                    'file_size': f['bytes'],
                    'file_events': f['events'],
                    'file_path': sel_path,
                    'created_at': datetime.now(),
                    'last_accessed_at': datetime.now()
                }
            })

    print(files)

    status = 'Failed'
    info = 'Request failed. No accessible files found for your dataset.'
    if files:
        status = 'Prescreened'
        info = str(len(files)) + ' files can be accessed.\n' + \
            str(files_skipped) + " files can't be accessed.\n" + \
            'Total size: ' + str(dataset_size) + '.\n'
        bulk(es, files)

    es.update(
        index='servicex',
        doc_type='docs',
        id=hit["_id"],
        body={
            'doc': {
                'status': status,
                'info': info,
                'dataset_size': dataset_size,
                'dataset_events': dataset_events,
                'dataset_files': len(files)
            }
        }
    )


# EXAMPLE RECORD
# {u'adler32': u'a32c162e',
#  u'name': u'DAOD_SUSY10.17038992._000098.pool.root.1',
#  u'rses': {
#      u'CERN-PROD_DATADISK': [
#          u'root://xcache.mwt2.org:1094//root://eosatlas.cern.ch:1094//eos/atlas/atlasdatadisk/rucio/mc16_13TeV/0e/20/DAOD_SUSY10.17038992._000098.pool.root.1'
#      ],
#      u'IN2P3-CC_DATADISK': [
#          u'root://xcache.mwt2.org:1094//root://ccxrdatlas.in2p3.fr:1094//pnfs/in2p3.fr/data/atlas/atlasdatadisk/rucio/mc16_13TeV/0e/20/DAOD_SUSY10.17038992._000098.pool.root.1'
#      ], u'MWT2_UC_LOCALGROUPDISK': [
#          u'root://fax.mwt2.org:1094//pnfs/uchicago.edu/atlaslocalgroupdisk/rucio/mc16_13TeV/0e/20/DAOD_SUSY10.17038992._000098.pool.root.1'
#      ]
#  },
#  u'bytes': 5987185696,
#  u'states': {
#      u'CERN-PROD_DATADISK': u'AVAILABLE',
#      u'IN2P3-CC_DATADISK': u'AVAILABLE',
#      u'MWT2_UC_LOCALGROUPDISK': u'AVAILABLE'
#  },
#  u'pfns': {
#      u'root://xcache.mwt2.org:1094//root://eosatlas.cern.ch:1094//eos/atlas/atlasdatadisk/rucio/mc16_13TeV/0e/20/DAOD_SUSY10.17038992._000098.pool.root.1':
#      {
#          u'domain': u'wan',
#          u'rse': u'CERN-PROD_DATADISK',
#          u'priority': 2,
#          u'volatile': False,
#          u'client_extract': False,
#          u'type': u'DISK'
#      },
#      u'root://xcache.mwt2.org:1094//root://ccxrdatlas.in2p3.fr:1094//pnfs/in2p3.fr/data/atlas/atlasdatadisk/rucio/mc16_13TeV/0e/20/DAOD_SUSY10.17038992._000098.pool.root.1':
#      {
#          u'domain': u'wan',
#          u'rse': u'IN2P3-CC_DATADISK',
#          u'priority': 3,
#          u'volatile': False,
#          u'client_extract': False,
#          u'type': u'DISK'
#      },
#      u'root://fax.mwt2.org:1094//pnfs/uchicago.edu/atlaslocalgroupdisk/rucio/mc16_13TeV/0e/20/DAOD_SUSY10.17038992._000098.pool.root.1':
#      {
#          u'domain': u'lan',
#          u'rse': u'MWT2_UC_LOCALGROUPDISK',
#          u'priority': 1,
#          u'volatile': False,
#          u'client_extract': False,
#          u'type': u'DISK'}
#  },
#     u'scope': u'mc16_13TeV',
#     u'md5': None
#  }
