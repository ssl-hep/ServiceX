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
from servicex.elasticsearch_adaptor import ElasticSearchAdapter


class TestElasticSearchAdaptor:
    def test_init(self, mocker):

        mock_es = mocker.patch('elasticsearch.Elasticsearch')
        ElasticSearchAdapter('localhost', '9999', 'foo', 'bar')
        mock_es.assert_called_with(hosts=['localhost:9999'], http_auth=('foo', 'bar'))

    def test_create_update_request(self, mocker):
        import elasticsearch
        mock_es = mocker.MagicMock(elasticsearch.Elasticsearch)
        mocker.patch.object(elasticsearch, 'Elasticsearch', return_value=mock_es)
        adaptor = ElasticSearchAdapter('localhost', '9999', 'foo', 'bar')

        adaptor.create_update_request("123-456", {
            'name': 'my-nane',
            'description': 'this is a test'
        })

        mock_es.index.assert_called_with(
            body={
                'name': 'my-nane',
                'description': 'this is a test'
            },
            index='servicex',
            id='123-456',
        )

    def test_create_update_path(self, mocker):
        import elasticsearch
        mock_es = mocker.MagicMock(elasticsearch.Elasticsearch)
        mocker.patch.object(elasticsearch, 'Elasticsearch', return_value=mock_es)
        adaptor = ElasticSearchAdapter('localhost', '9999', 'foo', 'bar')

        adaptor.create_update_path("123-456", {
            'name': 'my-nane',
            'description': 'this is a test'
        })

        mock_es.index.assert_called_with(
            body={
                'name': 'my-nane',
                'description': 'this is a test'
            },
            index='servicex_paths',
            id='123-456',
        )
