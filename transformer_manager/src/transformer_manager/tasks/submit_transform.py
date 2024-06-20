# Copyright (c) 2022, IRIS-HEP
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
from transformer_manager.dataset_manager import DatasetManager
from transformer_manager.did_parser import DIDParser
from transformer_manager.app import app
from transformer_manager.servicex_task import ServiceXTask


@app.task(base=ServiceXTask, bind=True, name='transformer_manager.submit_transform')
def submit_transform(self, message: dict):
    with self.Session(bind=self.engine) as session:
        request = message['request']
        print("Request received", request)
        did = request.get('did', "")
        file_list = request.get("file-list")
        request_id = request.get('request_id', "")

        if did:
            parsed_did = DIDParser(did,
                                   default_scheme=app.conf['did_finder_default_scheme'])
            if parsed_did.scheme not in app.conf['valid_did_schemes']:
                msg = f"DID scheme is not supported: {parsed_did.scheme}"
                raise Exception(msg)

            dataset_manager = DatasetManager.from_did(parsed_did,
                                                      logger=self.logger,
                                                      extras={
                                                          'requestId': request_id
                                                      }, db=self.session)
        else:  # no dataset, only a list of files given
            dataset_manager = DatasetManager.from_file_list(file_list,
                                                            logger=self.logger,
                                                            extras={
                                                                'requestId': request_id
                                                            }, db=session)
        print(dataset_manager)
        session.commit()


if __name__ == '__main__':
    args = ['worker', '--loglevel=INFO', '-n', 'submit_transform@%h']
    print(app.tasks)
    app.worker_main(argv=args)
