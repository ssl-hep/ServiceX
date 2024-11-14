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

from typing import List, Mapping, Optional, Tuple
from socket import gethostbyname
import math
from functools import lru_cache
import tempfile
from urllib.parse import urlparse
import geoip2.database
import geoip2.errors

logger = logging.getLogger('ReplicaDistanceService')


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float):
    ''' Assume inputs are in degrees; will convert to radians. Returns distance in radians '''
    dellat = math.radians(lat2-lat1)
    dellon = math.radians(lon2-lon1)
    hav_theta = ((1-math.cos(dellat))/2 +
                 math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*(1-math.cos(dellon))/2)

    return 2*math.asin(math.sqrt(hav_theta))


@lru_cache
def _get_distance(reader: Optional[geoip2.database.Reader],
                  fqdn: str, my_lat: float, my_lon: float):
    """
    Determine angular distance between server at fqdn and (my_lat, my_lon).
    If there is a failure of fdqn location lookup, will return pi
    """
    if reader is None:
        return math.pi
    try:
        loc_data = reader.city(gethostbyname(fqdn)).location
    except geoip2.errors.AddressNotFoundError as e:
        logger.warning(f'Cannot geolocate {fqdn}, returning maximum distance.\nError: {e}')
        return math.pi
    site_lat, site_lon = loc_data.latitude, loc_data.longitude
    if site_lat is None or site_lon is None:
        return math.pi
    return _haversine_distance(site_lat, site_lon, my_lat, my_lon)


class ReplicaSorter(object):
    _reader: Optional[geoip2.database.Reader] = None
    # we keep the temporary directory around so it won't get randomly deleted by the GC
    _tmpdir: Optional[tempfile.TemporaryDirectory] = None

    def __init__(self, db_url_tuple: Optional[Tuple[str, bool]] = None):
        """
        Argument is an optional tuple of (URL, bool).
        The URL is assumed to be a file to download; the bool indicates whether
        it is ready to be used (True) or needs unpacking (False)
        """
        if db_url_tuple is None:
            db_url_tuple = self.get_download_url_from_environment()
        self._download_data(db_url_tuple)

    def sort_replicas(self, replicas: List[str], location: Mapping[str, float]) -> List[str]:
        """
        Main method of this class.
        replicas: list of strings which are the URLs for the replicas for a file
        location: dict of the form {'latitude': xxx, 'longitude': yyy} where xxx and yyy are floats
        giving the latitude and longitude in signed degrees
        """
        if not self._reader:
            return replicas
        if len(replicas) == 1:
            return replicas
        fqdns = [(urlparse(replica).hostname, replica) for replica in replicas]
        distances = [(_get_distance(self._reader, fqdn, location['latitude'],
                                    location['longitude']),
                      replica) for fqdn, replica in fqdns]
        distances.sort()
        return [replica for _, replica in distances]

    @classmethod
    def get_download_url_from_key_and_edition(cls, license_key: str, edition: str):
        """
        Construct the (url, unpacked) tuple to feed to the constructor from a license key
        and an edition of the MaxMind database.
        """
        return (('https://download.maxmind.com/app/geoip_download?'
                f'edition_id={edition}&license_key={license_key}&suffix=tar.gz'),
                False)

    @classmethod
    def get_download_url_from_environment(cls) -> Optional[Tuple[str, bool]]:
        """
        Based on environment variables, this will give a tuple of the URL and a bool which is
        True if the file from the URL is ready to use as is, False if needs to be unpacked
        """
        if url := os.environ.get('GEOIP_DB_URL', ''):
            return (url, True)
        key = os.environ.get('GEOIP_DB_LICENSE_KEY', '')
        edition = os.environ.get('GEOIP_DB_EDITION', '')
        if (key and edition):
            return cls.get_download_url_from_key_and_edition(key, edition)
        else:
            return None

    def _download_data(self, db_url_tuple: Optional[Tuple[str, bool]]) -> None:
        """
        Retrieves and unpacks the MaxMind databases and initializes the GeoIP reader
        """
        from urllib.request import urlretrieve
        import tarfile
        import glob
        if db_url_tuple is None:
            return
        url, unpacked = db_url_tuple
        try:
            fname, _ = urlretrieve(url)
        except Exception as e:
            logger.error(f'Failure retrieving GeoIP database {url}.\nError: {e}')
            return
        try:
            if unpacked:
                self._reader = geoip2.database.Reader(fname)
            else:
                tarball = tarfile.open(fname)
                self._tmpdir = tempfile.TemporaryDirectory()
                tarball.extractall(self._tmpdir.name)
                self._reader = geoip2.database.Reader(glob.glob(os.path.join(self._tmpdir.name,
                                                                             '*/*mmdb')
                                                                )[0])
        except Exception as e:
            logger.error(f'Failure initializing the GeoIP database reader.\nError: {e}')
            self._reader = None
            return
