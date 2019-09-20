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
from flask import current_app
from flask import request
from flask_restful import Resource, reqparse

from servicex.models import TransformRequest, TransformationResult

parser = reqparse.RequestParser()
parser.add_argument('did', help='This field cannot be blank',
                    required=True)
parser.add_argument('columns', help='This field cannot be blank',
                    required=True)
parser.add_argument('image', required=False)
parser.add_argument('chunk-size', required=False, type=int)
parser.add_argument('workers', required=False, type=int)
parser.add_argument('messaging-backend', required=False)
parser.add_argument('kafka-broker', required=False)


def _generate_advertised_endpoint(endpoint):
    return "http://" + current_app.config['ADVERTISED_HOSTNAME'] + "/" + endpoint


class TransformerFileComplete(Resource):
    @classmethod
    def make_api(cls, transformer_manager):
        cls.transformer_manager = transformer_manager
        return cls

    def put(self, request_id):
        info = request.get_json()
        submitted_request = TransformRequest.return_request(request_id)
        rec = TransformationResult(
            did=submitted_request.did,
            request_id=request_id,
            file_path=info['file-path'],
            transform_status=info['status'],
            transform_time=info['total-time'],
            messages=info['num-messages']
        )
        rec.save_to_db()

        files_remaining = TransformRequest.files_remaining(request_id)
        if files_remaining and files_remaining <= 0:
            namepsace = current_app.config['TRANSFORMER_NAMESPACE']
            print("Job is all done... shutting down transformers")
            self.transformer_manager.shutdown_transformer_job(request_id, namepsace)
        print(info)
        return "Ok"
