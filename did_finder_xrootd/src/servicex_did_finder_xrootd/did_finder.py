import os
import logging
from typing import Any, AsyncGenerator, Dict
from XRootD import client as xrd

from servicex_did_finder_lib import start_did_finder

__log = logging.getLogger(__name__)

cache_prefix = os.environ.get('CACHE_PREFIX', '')


async def find_files(did_name: str,
                     info: Dict[str, Any]
                     ) -> AsyncGenerator[Dict[str, Any], None]:
    '''For each incoming XRootD glob specification, generate a list of files that ServiceX can
    process

    Notes:

    Args:
        did_name (str): Dataset name
        into (Dict[str, Any]): Information bag, mainly has the `request-id` which is
                               used to track error mesages accross logs.

    Returns:
        AsyncGenerator[Dict[str, any], None]: yield each file
    '''
    __log.info('DID Lookup request received.', extra={
               'requestId': info['request-id'], 'dataset': did_name})

    urls = xrd.glob(cache_prefix + did_name)
    if len(urls) == 0:
        raise RuntimeError(f"No files found matching {did_name} for request "
                           f"{info['request-id']} - are you sure it is correct?")

    for url in urls:
        yield {
            'paths': [url],
            'adler32': 0,  # No clue
            'file_size': 0,  # We could look up the size but that would be slow
            'file_events': 0,  # And this we do not know
        }


def run_xrootd():
    __log.info('Starting XRootD DID finder')
    try:
        __log.info('Starting XRootD DID finder',
                   extra={'requestId': 'forkingfork'})
        start_did_finder('xrootd', find_files)
    finally:
        __log.info('Done running XRootD DID finder')


if __name__ == "__main__":
    run_xrootd()
