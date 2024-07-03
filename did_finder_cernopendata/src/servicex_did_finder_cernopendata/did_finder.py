import argparse
import os
import logging
from subprocess import PIPE, Popen, STDOUT
from typing import Any, AsyncGenerator, Dict, Generator
from servicex_did_finder_lib import DIDFinderApp

__log = logging.getLogger(__name__)

cache_prefix = os.environ.get('CACHE_PREFIX', '')


def find_files(did_name: str,
                     info: Dict[str, Any],
                     did_finder_args: dict = None
               ) -> Generator[Dict[str, Any], None, None]:
    '''For each incoming did name, generate a list of files that ServiceX can
    process

    Notes:

        - Using command recommended (here)
          [https://opendata-forum.cern.ch/t/accessing-the-contents-of-a-record-via-a-web-api/58]
          to get files.

    Args:
        did_name (str): Dataset name
        info (Dict[str, Any]): Information bag, mainly has the `request-id` which is
                               used to track error mesages accross logs.
        command (str): Command to execute to get the did information. Used only for testing.

    Returns:
        AsyncGenerator[Dict[str, any], None]: yield each file
    '''

    if not did_name.isnumeric():
        raise Exception('CERNOpenData can only work with dataset numbers as names (e.g. 1507)')

    cmd = f'cernopendata-client get-file-locations --recid {did_name}'.split(" ")

    with Popen(cmd, stdout=PIPE, stderr=STDOUT, bufsize=1,universal_newlines=True) as p:
        assert p.stdout is not None
        all_lines = []
        non_root_uri = False
        for line in p.stdout:
            assert isinstance(line, str)
            all_lines.append(line)
            uri = line.strip()
            if uri.startswith('XXXXXXXhttp://') and cache_prefix == '':
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


def run_open_data():
    # Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--foo', dest='foo', action='store',
                        default='',
                        help='Prefix to add to Xrootd URLs')

    DIDFinderApp.add_did_finder_cnd_arguments(parser)

    __log.info('Starting CERNOpenData DID finder')
    app = DIDFinderApp('cernopendata', parsed_args=parser.parse_args())

    @app.did_lookup_task(name="did_finder_cern_opendata.lookup_dataset")
    def lookup_dataset(self, did: str, dataset_id: int, endpoint: str) -> None:
        self.do_lookup(did=did, dataset_id=dataset_id,
                       endpoint=endpoint, user_did_finder=find_files)

    app.start()


if __name__ == "__main__":
    run_open_data()
