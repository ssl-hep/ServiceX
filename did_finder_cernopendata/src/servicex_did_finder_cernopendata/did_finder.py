import logging
from subprocess import PIPE, Popen, STDOUT
from typing import Any, AsyncGenerator, Dict

from servicex_did_finder_lib import start_did_finder

__log = logging.getLogger(__name__)


async def find_files(did_name: str, info: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    '''For each incoming did name, generate a list of files that ServiceX can
    process

    Notes:

        - Using command recommenced (here)
          [https://opendata-forum.cern.ch/t/accessing-the-contents-of-a-record-via-a-web-api/58]
          to get files.

    Args:
        did_name (str): Dataset name

    Returns:
        AsyncGenerator[Dict[str, any], None]: yield each file
    '''
    __log.info(f'DID Lookup request for dataset {did_name}',
               extra={'requestId': info['request-id']})
    if not did_name.isnumeric():
        raise Exception('CERNOpenData can only work with dataset numbers as names (e.g. 1507)')

    cmd = f'cernopendata-client get-file-locations --protocol xrootd --recid {did_name}'.split(' ')
    print(cmd)

    with Popen(cmd, stdout=PIPE, stderr=STDOUT, bufsize=1,
               universal_newlines=1) as p:  # type: ignore

        for line in p.stdout:
            assert isinstance(line, str)
            uri = line.strip()
            if not uri.startswith('root://'):
                raise Exception(f'CMSOpenData: Opendata record returned a non-xrootd url: {uri}')
            yield {
                'file_path': uri,
                'adler32': 0,  # No clue
                'file_size': 0,  # Size in bytes if known
                'file_events': 0,  # Number of events if known
            }


def run_open_data():
    __log.info('Starting CERNOpenData DID finder')
    try:
        __log.info('Starting CERNOpenData DID finder',
                   extra={'requestId': 'forkingfork'})
        start_did_finder('cernopendata', find_files)
    finally:
        __log.info('Done running CERNOpenData DID finder')


if __name__ == "__main__":
    run_open_data()
