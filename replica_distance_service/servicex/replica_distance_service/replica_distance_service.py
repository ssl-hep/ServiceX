# Copyright (c) 2024, IRIS-HEP
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
import logging
import os

from typing import List, Mapping, Union, Optional, Tuple
from socket import gethostbyname
import math
from functools import lru_cache

import kombu
from celery import Celery, shared_task
import timeit
from urllib.parse import urlparse
import geoip2.database

from argparse import Namespace, ArgumentParser
from types import SimpleNamespace


logger = logging.getLogger('ReplicaDistanceService')

reader: Optional[geoip2.database.Reader] = None
celery_app: Optional[Celery] = None


def haversine_distance(lat1, lon1, lat2, lon2):
    ''' Assume inputs are in degrees; will convert to radians. Returns distance in radians '''
    dellat = math.radians(lat2-lat1)
    dellon = math.radians(lon2-lon1)
    hav_theta = ((1-math.cos(dellat))/2 + 
                 math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*(1-math.cos(dellon))/2)

    return 2*math.asin(math.sqrt(hav_theta))


@lru_cache
def get_distance(fqdn: str, my_lat: float, my_lon: float):
    global reader
    if reader is None:
        return math.pi
    loc_data = reader.city(gethostbyname(fqdn)).location
    site_lat, site_lon = loc_data.latitude, loc_data.longitude
    return haversine_distance(site_lat, site_lon, my_lat, my_lon)


@shared_task(name="order_replicas")
def lookup_dataset(replicas: List[str], location: Mapping[str, str]) -> List[str]:
    global reader
    if not reader:
        return replicas
    fqdns = [(urlparse(replica).hostname, replica) for replica in replicas]
    distances = [(get_distance(fqdn, location['latitude'], location['longitude']),
                  replica) for fqdn, replica in fqdns]
    distances.sort()

    return [replica for _, replica in distances]


def get_download_url() -> Optional[Tuple[str, bool]]:
    """ This will give the URL and True if it is ready to use, False if needs to be unpacked """
    if url := os.environ.get('GEOIP_DB_URL', ''):
        return (url, True)
    key = os.environ.get('GEOIP_DB_LICENSE_KEY', '')
    edition = os.environ.get('GEOIP_DB_EDITION', '')
    if (key and edition):
        return (('https://download.maxmind.com/app/geoip_download?'
                 f'edition_id={edition}&license_key={key}&suffix=tar.gz'),
                False)
    else:
        return None


def download_data() -> None:
    global reader
    from urllib.request import urlretrieve
    import tarfile
    import glob
    if (urlinfo := get_download_url()) is None:
        return
    url, unpacked = urlinfo
    fname, _ = urlretrieve(url)
    if unpacked:
        reader = geoip2.database.Reader(fname)
    else:
        tarball = tarfile.open(fname)
        tarball.extractall()
        reader = geoip2.database.Reader(glob.glob('*/*mmdb')[0])


def init() -> None:
    global celery_app
    parser = ArgumentParser(description="ServiceX Transformer")
    parser.add_argument('--rabbit_uri', help='URL for RabbitMQ')
    _args = parser.parse_args()
    app = Celery("replica_distance_service", broker=_args.rabbit_uri)
    app.conf.task_queues = [
        kombu.Queue(name="replica_distance_service",
                    durable=True)
    ]
    app.conf.task_create_missing_queues = False
    app.conf.worker_hijack_root_logger = False
    app.conf.worker_redirect_stdouts_level = 'DEBUG'
    app.conf.worker_prefetch_multiplier = 1
    app.conf.broker_connection_retry_on_startup = True

    celery_app = app

    logger.info("Starting download of GeoIP data")
    download_data()

    logger.info(
        "Replica distance service startup finished. Will now start listening for requests"
    )

    app.worker_main(
        argv=[
            "worker",
            "--concurrency=1",  # Don't allow multiple files to be processed at once
            "--without-mingle",
            "--without-gossip",
            "--without-heartbeat",
            "--loglevel=info",
            "-Q", "replica_distance_service",
            "-n", "replica_distance_service@%h",
        ]
    )


if __name__ == "__main__":  # pragma: no cover
    init()
    exit(0)
