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
import logging

from transformer_sidecar.servicex_adapter import ServiceXAdapter


class TestServiceXAdapter:

    def test_init(self, mocker):
        import requests
        mock_session = mocker.MagicMock(requests.session)
        mocker.patch('requests.session', return_value=mock_session)
        mock_session.mount = mocker.Mock()
        ServiceXAdapter("http://foo.com")
        retries = mock_session.mount.mock_calls[0][1][1].max_retries
        assert retries.total == 5
        assert retries.connect == 3

    def test_put_file_complete(self, mocker, caplog):
        import requests
        caplog.set_level(logging.INFO)
        mock_session = mocker.MagicMock(requests.session)
        mock_session.mount = mocker.Mock()
        mock_session.put = mocker.Mock()
        mocker.patch('requests.session', return_value=mock_session)

        adapter = ServiceXAdapter("http://foo.com")
        adapter.put_file_complete("req_id", "my-root.root", 42, "testing", 1, 2, 3, 4)
        mock_session.put.assert_called()
        args = mock_session.put.call_args
        assert args[0][0] == 'http://foo.com/file-complete'
        doc = args[1]['json']
        assert doc['status'] == 'testing'
        assert doc['total-events'] == 3
        assert doc['total-time'] == 2
        assert doc['file-path'] == 'my-root.root'
        assert doc['file-id'] == 42
        assert doc['avg-rate'] == 1

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.INFO
        assert caplog.records[0].msg == "Put file complete."

    def test_put_file_complete_retry(self, mocker, caplog):
        import requests
        caplog.set_level(logging.INFO)
        mock_session = mocker.MagicMock(requests.session)
        mock_session.mount = mocker.Mock()
        mock_session.put = mocker.Mock(side_effect=[requests.exceptions.ConnectionError, 200])
        mocker.patch('requests.session', return_value=mock_session)

        adapter = ServiceXAdapter("http://foo.com")
        adapter.put_file_complete("req_id", "my-root.root", 42, "testing", 1, 2, 3, 4)
        assert mock_session.put.call_count == 2
        assert len(caplog.records) == 2
        assert caplog.records[0].levelno == logging.WARNING
        assert caplog.records[0].msg == '%s, retrying in %s seconds...'
        assert caplog.records[1].levelno == logging.INFO
        assert caplog.records[1].msg == "Put file complete."
