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

GEOIP_URL = 'https://ponyisi.web.cern.ch/public/GeoLite2-City.mmdb'
GEOIP_TGZ_URL = 'https://ponyisi.web.cern.ch/public/GeoLite2-City_20241015.tar.gz'

# some URLs (real FQDNs, not real file paths)
REPLICAS = ['https://ccxrootdatlas.in2p3.fr:1094//pnfs/DAOD_PHYSLITE.37020764._000004.pool.root.1',
            'root://fax.mwt2.org:1094//DAOD_PHYSLITE.37020764._000004.pool.root.1',
            'root://atlasdcache-kit.gridka.de:1094//DAOD_PHYSLITE.37020764._000004.pool.root.1']

SORTED_REPLICAS = ['root://fax.mwt2.org:1094//DAOD_PHYSLITE.37020764._000004.pool.root.1',
                   'https://ccxrootdatlas.in2p3.fr:1094//pnfs/DAOD_PHYSLITE.37020764._000004.pool.root.1',  # noqa: E501
                   'root://atlasdcache-kit.gridka.de:1094//DAOD_PHYSLITE.37020764._000004.pool.root.1']  # noqa: E501

JUNK_REPLICAS = ['https://junk.does.not.exist.org/',
                 'root://fax.mwt2.org:1094//pnfs/uchicago.edu/']
SORTED_JUNK_REPLICAS = ['root://fax.mwt2.org:1094//pnfs/uchicago.edu/',
                        'https://junk.does.not.exist.org/']

LOCATION = {'latitude': 41.78, 'longitude': -87.7}


def test_sorting():
    """Also test unpacking tgz database"""
    from rucio_did_finder.replica_distance import ReplicaSorter
    rs = ReplicaSorter((GEOIP_TGZ_URL, False))
    # Given location (Chicago) replicas should sort US, FR, DE
    sorted = rs.sort_replicas(REPLICAS, LOCATION)
    assert sorted == SORTED_REPLICAS
    # the nonexistent FQDN should sort at end
    sorted = rs.sort_replicas(JUNK_REPLICAS, LOCATION)
    assert sorted == SORTED_JUNK_REPLICAS


def test_envvars():
    """Only tests unpacked DB download"""
    from rucio_did_finder.replica_distance import ReplicaSorter
    import os
    os.environ['GEOIP_DB_URL'] = GEOIP_URL
    rs = ReplicaSorter()
    sorted = rs.sort_replicas(REPLICAS, LOCATION)
    assert sorted == SORTED_REPLICAS
    del os.environ['GEOIP_DB_URL']


def test_bad_geodb():
    """Tests what happens when we have a bad DB URL"""
    from rucio_did_finder.replica_distance import ReplicaSorter
    rs = ReplicaSorter(('https://junk.does.not.exist.org', False))
    assert rs._database is None
    sorted = rs.sort_replicas(REPLICAS, LOCATION)
    assert sorted == REPLICAS
