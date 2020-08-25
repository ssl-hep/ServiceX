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
import sys
import time
import hashlib
import hmac

from flask_jwt_extended import get_jwt_identity
from flask_restful import Resource
from flask import current_app
from datetime import datetime
from datetime import timezone

from servicex.models import TransformationResult, UserModel


class ServiceXResource(Resource):
    @classmethod
    def _generate_advertised_endpoint(cls, endpoint):
        return "http://" + current_app.config['ADVERTISED_HOSTNAME'] + "/" + endpoint

    @staticmethod
    def _validate_user():
        """
        Determine if the session should allow the user request in.
        :return: Tuple of Boolean indicating whether the permission is granted and
        a string message of why it is rejected
        """
        if not current_app.config['ENABLE_AUTH']:
            return True, None
        try:
            sub = get_jwt_identity()
            if not sub:
                return False, "No auth provided"
            user = UserModel.find_by_sub(sub)
            if user and not user.pending:
                return True, None
            else:
                return False, "No Valid Auth Provided"
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print(exc_value)
            return False, str(exc_value)

    @staticmethod
    def _verify_slack_request(req):
        secret = current_app.config.get('SLACK_SIGNING_SECRET')
        if not secret:
            return False, "No Slack app configured"

        body = req.get_data().decode('utf-8')

        timestamp = req.headers['X-Slack-Request-Timestamp']
        if time.time() - float(timestamp) > 60 * 5:
            return False, "Request is expired"

        sig_basestring = f"v0:{timestamp}:{body}".encode('utf-8')
        signature = "v0=" + hmac.new(secret.encode('utf-8'),
                                     sig_basestring,
                                     digestmod=hashlib.sha256).hexdigest()
        slack_signature = req.headers['X-Slack-Signature']
        if hmac.compare_digest(signature, slack_signature):
            return True, None
        else:
            return False, "Signatures did not match"

    @staticmethod
    def _generate_file_status_record(dataset_file, status):
        time = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

        return {
            "req_id": dataset_file.request_id,
            "adler32": dataset_file.adler32,
            "file_size": dataset_file.file_size,
            "file_events": dataset_file.file_events,
            "file_path": dataset_file.file_path,
            "status": status,
            "info": 'info',
            "created_at": time,
            "last_accessed_at": time,
            "events_served": 0,
            "retries": 0
        }

    def _generate_transformation_record(self, submitted_request, status):
        request_id = submitted_request.request_id
        count = TransformationResult.count(request_id)
        time = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        current_stats = TransformationResult.statistics(request_id)

        events_transformed = 0 if not current_stats else current_stats['total-events']
        return {
            "name": 'Transformation Request',
            "description": 'Transformation Request',
            "dataset": submitted_request.did,
            "dataset_size": int(submitted_request.total_bytes or 0),
            "dataset_files": count,
            "dataset_events": int(submitted_request.total_events or 0),
            "columns": submitted_request.columns,
            "events": 0,
            "events_transformed": events_transformed,
            "events_served": 0,
            "events_processed": 0,
            "created_at": submitted_request.submit_time,
            "modified_at": time,
            "status": status,
            "info": ' '
        }
