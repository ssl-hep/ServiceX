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
from datetime import datetime, timezone

from flask_restful import reqparse
from flask import jsonify

from servicex.decorators import auth_required
from servicex.models import TransformationResult, TransformRequest, db
from servicex.resources.servicex_resource import ServiceXResource


status_request_parser = reqparse.RequestParser()
status_request_parser.add_argument('details', type=bool, default=False,
                                   required=False, location='args')


class TransformationStatus(ServiceXResource):
    @auth_required
    def get(self, request_id):
        transform = TransformRequest.lookup(request_id)
        if not transform:
            msg = f'Transformation request not found with id: {request_id}'
            return {'message': msg}, 404

        status_request = status_request_parser.parse_args()

        # Format timestamps with military timezone, given that they are in UTC.
        # See https://stackoverflow.com/a/42777551/8534196
        iso_fmt = '%Y-%m-%dT%H:%M:%S.%fZ'
        result_dict = {
            "status": transform.status,
            "request-id": request_id,
            "submit-time": transform.submit_time.strftime(iso_fmt),
            "finish-time": transform.finish_time,
            "files-processed": transform.files_processed,
            "files-skipped": transform.files_failed,
            "files-remaining": transform.files_remaining,
            "stats": transform.statistics
        }
        if transform.finish_time is not None:
            result_dict["finish-time"] = transform.finish_time.strftime(iso_fmt)

        if status_request.details:
            result_dict['details'] = TransformationResult.to_json_list(
                transform.results
            )

        return jsonify(result_dict)


# Status Updates POST
status_parser = reqparse.RequestParser()
status_parser.add_argument('timestamp', help='This field cannot be blank',
                           required=True)
status_parser.add_argument('severity', help='Should be debug, info, warn, or fatal',
                           required=False)
status_parser.add_argument('info', required=False)
status_parser.add_argument('source', required=False)


class TransformationStatusInternal(ServiceXResource):

    def post(self, request_id):
        status = status_parser.parse_args()
        status.request_id = request_id
        if status.severity == "fatal":
            print("+--------------------------------------------+")
            print(r"""
  ______   _______       _        ______ _____  _____   ____  _____
 |  ____/\|__   __|/\   | |      |  ____|  __ \|  __ \ / __ \|  __ \
 | |__ /  \  | |  /  \  | |      | |__  | |__) | |__) | |  | | |__) |
 |  __/ /\ \ | | / /\ \ | |      |  __| |  _  /|  _  /| |  | |  _  /
 | | / ____ \| |/ ____ \| |____  | |____| | \ \| | \ \| |__| | | \ \
 |_|/_/    \_\_/_/    \_\______| |______|_|  \_\_|  \_\\____/|_|  \_\
            """)
            print(f"+ Fatal error reported for {request_id} from {status.source}")
            print(status.info)
            print("+--------------------------------------------+")

            submitted_request = TransformRequest.lookup(request_id)
            submitted_request.status = 'Fatal'
            submitted_request.finish_time = datetime.now(tz=timezone.utc)
            submitted_request.failure_description = status.info
            submitted_request.save_to_db()
            db.session.commit()
        else:
            print(status)
