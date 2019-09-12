import time
from Queue import Queue
from threading import Thread
import json
from rucio.client import ReplicaClient
from rucio.client import DIDClient
from rucio.common import exception as rucioe
import requests


N_THREADS = 10
file_queue = Queue()

# needed for python2
try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

with open('config/config.json') as json_file:
    CONF = json.load(json_file)

print('configuration:\n', CONF)

print('sleeping until CAs are there...')

time.sleep(60)

counters = {
    'files': 0,
    'found': 0,
    'skipped': 0
}


def get_replicas(i, q):
    while True:
        f = q.get()
        print('%s: Looking up:' % i, f)

        f_scope = f['scope']
        f_name = f['name']

        try:
            g_replicas = rc.list_replicas(
                dids=[{'scope': f_scope, 'name': f_name}],
                schemes=['root'],
                client_location={'site': CONF['SITE']})
        except rucioe.DatabaseException as rdbe:
            print('DatabaseException caught. Putting back in queue and slowing down.', rdbe)
            time.sleep(5)
            q.put(f)
            q.task_done()
            continue
        except Exception as exc:
            print('could not find file replica. Skipping file:', f_name, exc)
            counters['skipped'] += 1
            q.task_done()
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
                counters['skipped'] += 1
                continue

            data = {
                'req_id': REQ["reqId"],
                'adler32': f['adler32'],
                'file_size': f['bytes'],
                'file_events': f['events'],
                'file_path': sel_path
            }
            print(data)
            break

        cr_status = requests.post('https://' + CONF['SITENAME'] + '/dpath/create', json=data, verify=False)
        print('cr_status:', cr_status)
        counters['found'] += 1

        q.task_done()


while True:
    try:
        RES = requests.get('https://' + CONF['SITENAME'] + '/drequest/status/Created', verify=False)
    except requests.exceptions.RequestException as re:
        print('could not access the service:', re)
        time.sleep(60)
        continue

    try:
        REQ = RES.json()
    except JSONDecodeError:
        print("N'est pas JSON: ", RES)
        time.sleep(10)
        continue

    if REQ is None:
        time.sleep(10)
        continue

    try:
        rc = ReplicaClient()
        dc = DIDClient()
    except Exception as ge:
        print('problem in getting rucio client', ge)
        time.sleep(60)
        continue

    print("processing request:\n", REQ)

    UPDATE_STATUS = requests.put('https://' + CONF['SITENAME'] + '/drequest/status/' +
                                 REQ['reqId'] + '/' + 'LookingUp/did-finder_started', verify=False)
    print('UPDATE_STATUS:', UPDATE_STATUS)
    if UPDATE_STATUS.status_code != 200:
        continue

    ds = REQ['dataset'].strip()
    (scope, name) = ds.split(":")
    try:
        g_files = dc.list_files(scope, name)
    except rucioe.DataIdentifierNotFound as didnf:
        print('could not find data set. Setting request to failed.', didnf)
        g_files = []
    except rucioe.CannotAuthenticate as cau:
        print('cant authenticate', cau)
    except Exception as exc:
        print('Unexpected error. Will retry. ', exc)

    # Set up threads to fetch replicas
    for i in range(N_THREADS):
        worker = Thread(target=get_replicas, args=(i, file_queue,))
        worker.setDaemon(True)
        worker.start()

    counters = {
        'files': 0,
        'found': 0,
        'skipped': 0
    }
    DATASET_SIZE = 0
    DATASET_EVENTS = 0
    for f in g_files:
        print(f)
        DATASET_SIZE += f['bytes']
        DATASET_EVENTS += f['events']
        counters['files'] += 1
        file_queue.put(f)

    file_queue.join()
    print('all threads done.')
    print('totals:', counters)

    status = 'Failed'
    info = 'Request failed. No accessible files found for your dataset.'
    if counters['found'] > 0:
        status = 'LookedUp'
        info = str(counters['found']) + ' files can be accessed.\n' + \
            str(counters['skipped']) + " files can't be accessed.\n" + \
            'Total size: ' + str(DATASET_SIZE) + '.\n'

    REQ_DATA = {
        'id': REQ["reqId"],
        'status': status,
        'info': info,
        'dataset_size': DATASET_SIZE,
        'dataset_events': DATASET_EVENTS,
        'dataset_files': counters['files']
    }

    print(REQ_DATA)

    RU_STATUS = requests.post('https://' + CONF['SITENAME'] + '/drequest/update', json=REQ_DATA, verify=False)
    print('RU_STATUS:', RU_STATUS)

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
