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
from flask import Response

# from tests.web.web_test_base import WebTestBase
# from servicex.web import api_token
# from servicex.web.decorators import authenticated
# from servicex.models import db, UserModel


# class TestApiToken(WebTestBase):
#     def test_api_token(self, mocker, client):
#         user = UserModel(
#             email='jane@example.com',
#             name='Jane Doe',
#             sub='oauth-subject-id',
#             refresh_token='jwt:refresh'
#         )
#         with client.application.app_context():
#             s = {
#                 'name': 'Jane Doe',
#                 'email': 'jane@example.com',
#                 'sub': 'oauth-subject-id',
#                 'is_authenticated': True
#             }
#             # session = self.mock_session(mocker, s)
#             db.session.commit = mocker.Mock()
#             UserModel.find_by_sub = mocker.Mock(return_value=user)
#             response: Response = client.get('/api-token')
#             print(response.data)
#             # assert response.status_code == 302
#             # print(user.__dict__)
#             assert user.refresh_token != 'jwt:refresh'
#             db.session.commit.assert_called()
