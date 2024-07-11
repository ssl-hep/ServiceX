import os
import logging
from subprocess import PIPE, Popen, STDOUT
from typing import Any, Dict, Generator

from servicex_did_finder_lib import DIDFinderApp

__log = logging.getLogger(__name__)

cache_prefix = os.environ.get('CACHE_PREFIX', '')

app = DIDFinderApp('cernopendata')


@app.did_lookup_task(name="did_finder_cernopendata.lookup_dataset")
def lookup_dataset(self, did: str, dataset_id: int, endpoint: str) -> None:
    self.do_lookup(did=did, dataset_id=dataset_id,
                   endpoint=endpoint, user_did_finder=find_files)


def find_files(did_name: str,
               info: Dict[str, Any],
               did_finder_args: dict = None) -> Generator[Dict[str, Any], None, None]:
    """
    For each incoming did name, generate a list of files that ServiceX can process

    Notes:

        - Using command recommended (here)
          [https://opendata-forum.cern.ch/t/accessing-the-contents-of-a-record-via-a-web-api/58]
          to get files.

    Args:
        did_name (str): Dataset name
        info (Dict[str, Any]): Information bag, mainly has the `request-id` which is
                               used to track error mesages accross logs.
        did_finder_args (dict): Additional arguments passed to the finder
    Returns:
        Generator[Dict[str, any], None]: yield each file
    """

    if not did_name.isnumeric():
        raise Exception('CERNOpenData can only work with dataset numbers as names (e.g. 1507)')

    cmd = f'cernopendata-client get-file-locations --recid {did_name}'.split(" ")

    with Popen(cmd, stdout=PIPE, stderr=STDOUT, bufsize=1, universal_newlines=True) as p:
        assert p.stdout is not None
        all_lines = []
        non_root_uri = False
        for line in p.stdout:
            assert isinstance(line, str)
            all_lines.append(line)
            uri = line.strip()
            if uri.startswith('http://') and cache_prefix == '':
                non_root_uri = True
            else:
                yield {
                    'paths': [cache_prefix + uri],
                    'adler32': 0,  # No clue
                    'file_size': 0,  # Size in bytes if known
                    'file_events': 0,  # Number of events if known
                }

        # Next, sort out the errors (if there are any)
        p.wait()
        if p.returncode != 0:
            raise Exception(f'CERN Open Data Lookup failed with error code {p.returncode}. '
                            'All returned output:'
                            '\n\t' + '\n\t'.join(all_lines))

        if non_root_uri:
            raise Exception('CMSOpenData: Opendata record returned a strange url'
                            '\n\t' + '\n\t'.join(all_lines))
