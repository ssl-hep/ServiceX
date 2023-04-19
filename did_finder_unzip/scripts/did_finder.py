# Copyright (c) 2019, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import argparse
import logging
import os
import json

from minio import Minio
from servicex_did_finder_lib import add_did_finder_cnd_arguments, start_did_finder


def run_rucio_finder():
    '''Run the rucio finder
    '''
    logger = logging.getLogger()

    # Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-logical-files", action="store_true")
    add_did_finder_cnd_arguments(parser)

    args = parser.parse_args()

    logger.info("ServiceX DID Finder starting up. ")
    print(args)
    if args.report_logical_files:
        logger.info("---- DID Finder Only Returning Logical Names, not replicas -----")

    # Run the DID Finder
    try:
        logger.info('Starting rucio DID finder')
        minio_url = os.environ.get("MINIO_URL")
        minio_secret_key = os.environ.get("MINIO_SECRET_KEY")
        minio_access_key = os.environ.get("MINIO_ACCESS_KEY")
        use_https = False

        async def callback(did_name, info):
            minio_client = Minio(endpoint=minio_url, access_key=minio_access_key,
                                      secret_key=minio_secret_key, secure=use_https)
            for file in minio_client.list_objects(did_name):
                url = minio_client.get_presigned_url(
                    "GET",
                    file.bucket_name,
                    file.object_name
                )
                return_obj = {
                    'adler32': 0,
                    'file_size': 0,
                    'file_events': 0,
                    'paths': [url]
                }
                yield return_obj

        start_did_finder('unzip',
                         callback,
                         parsed_args=args)

    finally:
        logger.info('Done running rucio DID finder')


if __name__ == "__main__":
    run_rucio_finder()