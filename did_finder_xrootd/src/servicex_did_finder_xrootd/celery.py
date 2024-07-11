import os
import logging
from typing import Any, Dict, Generator
from XRootD import client as xrd

from servicex_did_finder_lib import DIDFinderApp

__log = logging.getLogger(__name__)

cache_prefix = os.environ.get('CACHE_PREFIX', '')
app = DIDFinderApp('xrootd')


@app.did_lookup_task(name="did_finder_xrootd.lookup_dataset")
def lookup_dataset(self, did: str, dataset_id: int, endpoint: str) -> None:
    self.do_lookup(did=did, dataset_id=dataset_id,
                   endpoint=endpoint, user_did_finder=find_files)


def find_files(did_name: str, info: Dict[str, Any],
               did_finder_args: dict = None) -> Generator[Dict[str, Any], None, None]:
    """For each incoming XRootD glob specification, generate a list of files that ServiceX can
    process

    Notes:

    Args:
        did_name (str): Dataset name
        info (Dict[str, Any]): Information bag, mainly has the `request-id` which is
                               used to track error mesages accross logs.
        did_finder_args (dict): Additional arguments passed to the finder

    Returns:
        Generator[Dict[str, any], None]: yield each file
    """
    __log.info('DID Lookup request received.', extra={
               'dataset_id': info['dataset-id'], 'dataset': did_name})

    urls = xrd.glob(cache_prefix + did_name)
    if len(urls) == 0:
        raise RuntimeError(f"No files found matching {did_name} for dataset "
                           f"{info['dataset-id']} - are you sure it is correct?")

    for url in urls:
        yield {
            'paths': [url],
            'adler32': 0,  # No clue
            'file_size': 0,  # We could look up the size but that would be slow
            'file_events': 0,  # And this we do not know
        }
