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
import traceback

from flask import request

from servicex.models import TransformRequest, DatasetFile
from servicex.resources.servicex_resource import ServiceXResource


class AddFileToDataset(ServiceXResource):
    @classmethod
    def make_api(cls, lookup_result_processor):
        cls.lookup_result_processor = lookup_result_processor
        return cls

    def put(self, request_id):
        try:
            from servicex.models import db
            add_file_request = request.get_json()
            submitted_request = TransformRequest.lookup(request_id)

            db_record = DatasetFile(request_id=request_id,
                                    file_path=add_file_request['file_path'],
                                    adler32=add_file_request['adler32'],
                                    file_events=add_file_request['file_events'],
                                    file_size=add_file_request['file_size'])

            self.lookup_result_processor.add_file_to_dataset(submitted_request, db_record)

            db.session.commit()

            return {
                "request-id": str(request_id),
                "file-id": db_record.id
            }

        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            print(exc_value)
            return {'message': 'Something went wrong: ' + str(exc_value)}, 500
