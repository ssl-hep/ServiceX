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
import json


class LookupResultProcessor:
    def __init__(self, rabbitmq_adaptor, advertised_endpoint):
        self.rabbitmq_adaptor = rabbitmq_adaptor
        self.advertised_endpoint = advertised_endpoint

    def add_file_to_dataset(self, submitted_request, dataset_file):
        request_id = submitted_request.request_id
        dataset_file.save_to_db()

        transform_request = {
            'request-id': request_id,
            'file-id': dataset_file.id,
            'columns': submitted_request.columns,
            'paths': dataset_file.paths,
            'tree-name': submitted_request.tree_name,
            "service-endpoint": self.advertised_endpoint +
            "servicex/internal/transformation/" + request_id,
            "chunk-size": "1000",
            "result-destination": submitted_request.result_destination
        }

        self.rabbitmq_adaptor.basic_publish(exchange='transformation_requests',
                                            routing_key=request_id,
                                            body=json.dumps(transform_request))

    def report_fileset_complete(self, submitted_request,
                                num_files, num_skipped=0, total_events=0,
                                total_bytes=0, did_lookup_time=0):
        submitted_request.files = num_files
        submitted_request.files_skipped = num_skipped
        submitted_request.total_events = total_events
        submitted_request.total_bytes = total_bytes
        submitted_request.did_lookup_time = did_lookup_time
