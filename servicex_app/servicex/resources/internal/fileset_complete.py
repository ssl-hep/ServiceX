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

from servicex.models import Dataset, db
from servicex.resources.servicex_resource import ServiceXResource
# from servicex.resources.internal.transformer_file_complete import TransformerFileComplete


class FilesetComplete(ServiceXResource):
    @classmethod
    def make_api(cls, lookup_result_processor, transformer_manager):
        cls.lookup_result_processor = lookup_result_processor
        cls.transformer_manager = transformer_manager
        return cls

    def put(self, dataset_id):
        summary = request.get_json()
        dset = Dataset.find_by_id(dataset_id)
        current_app.logger.info("Completed fileset for datasetID",
                                extra={'dataset_id': dataset_id,
                                       'elapsed-time': summary['elapsed-time']})
        dset.n_files = summary['files']
        dset.events = summary['total-events']
        dset.size = summary['total-bytes']
        dset.complete = True
        dset.save_to_db()
        db.session.commit()

# TODO need a request id for this to work. Not sure if needed here.
        # if summary['files'] == 0:
        #     TransformerFileComplete.transform_complete(current_app.logger,
        #                                                dset,
        #                                                self.transformer_manager)
