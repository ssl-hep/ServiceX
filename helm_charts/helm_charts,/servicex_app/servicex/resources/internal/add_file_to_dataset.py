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
from flask import request, current_app

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
            # this request can be a single file dictionary
            # or a list of file dictionaries.
            add_file_request = request.get_json()
            submitted_request = TransformRequest.lookup(request_id)
            current_app.logger.info(f"Submitted request: {submitted_request}",
                                    extra={'requestId': request_id})

            # check if the request is bulk or single file
            if type(add_file_request) is dict:
                add_file_request = [add_file_request]

            for afr in add_file_request:
                db_record = DatasetFile(request_id=request_id,
                                        paths=','.join(afr['paths']),
                                        adler32=afr['adler32'],
                                        file_events=afr['file_events'],
                                        file_size=afr['file_size'])

                self.lookup_result_processor.add_file_to_dataset(submitted_request, db_record)

            db.session.commit()
            current_app.logger.info(f"Got {len(add_file_request)} files.",
                                    extra={'requestId': request_id})

            return {
                "request-id": str(request_id)
            }

        except Exception as e:
            current_app.logger.exception("Exception occurred when adding file to dataset",
                                         extra={'requestId': request_id})
            return {'message': f"Something went wrong: {e}"}, 500
