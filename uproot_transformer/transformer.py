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
import time

from servicex.transformer.servicex_adapter import ServiceXAdapter
from servicex.transformer.transformer_argument_parser import TransformerArgumentParser
from servicex.transformer.object_store_manager import ObjectStoreManager
from servicex.transformer.rabbit_mq_manager import RabbitMQManager
import os


# How many bytes does an average awkward array cell take up. This is just
# a rule of thumb to calculate chunksize
avg_cell_size = 42

object_store = None


# noinspection PyUnusedLocal
def callback(channel, method, properties, body):
    transform_request = json.loads(body)
    _request_id = transform_request['request-id']
    _file_path = transform_request['file-path']
    _file_id = transform_request['file-id']
    _server_endpoint = transform_request['service-endpoint']
    servicex = ServiceXAdapter(_server_endpoint)

    tick = time.time()
    try:
        # Do the transform
        root_file = _file_path.replace('/', ':')
        output_path = '/home/atlas/' + root_file
        transform_single_file(_file_path, output_path)

        tock = time.time()

        if object_store:
            object_store.upload_file(_request_id, root_file, output_path)
            os.remove(output_path)

        servicex. post_status_update("File " + _file_path + " complete")

        servicex.put_file_complete(_file_path, _file_id, "success",
                                   num_messages=0,
                                   total_time=round(tock - tick, 2),
                                   total_events=0,
                                   total_bytes=0)

    except Exception as error:
        transform_request['error'] = str(error)
        channel.basic_publish(exchange='transformation_failures',
                              routing_key=_request_id + '_errors',
                              body=json.dumps(transform_request))
        servicex.put_file_complete(file_path=_file_path, file_id=_file_id,
                                   status='failure', num_messages=0, total_time=0,
                                   total_events=0, total_bytes=0)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def transform_single_file(file_path, output_path):
    print("Transforming a single path: " + str(file_path) + " into " + output_path)
    os.system("set")
    os.system("ls $X509_USER_PROXY")
    os.system("voms-proxy-info --all")
    r = os.system('bash /generated/runner.sh -r -d ' + file_path + ' -o ' + output_path)
    if r != 0:
        raise BaseException("Unable to run the file - error return: " + str(r))


def compile_code():
    # Have to use bash as the file runner.sh does not execute properly, despite its 'x'
    # bit set. This seems to be some vagary of a ConfigMap from k8, which is how we usually get
    # this file.
    r = os.system('bash /generated/runner.sh -c')
    if r != 0:
        raise BaseException("Unable to compile the code - error return: "
                            + str(r))


if __name__ == "__main__":
    parser = TransformerArgumentParser(description="xAOD CPP Transformer")
    args = parser.parse_args()

    assert args.result_format == 'root-file', 'We only know how to create root file output'
    assert args.result_destination != 'kafka', 'Kafka not yet supported'

    if not args.output_dir and args.result_destination == 'object-store':
        messaging = None
        object_store = ObjectStoreManager()

    compile_code()

    if args.request_id and not args.path:
        rabbitmq = RabbitMQManager(args.rabbit_uri, args.request_id, callback)

    if args.path:
        transform_single_file(args.path, args.output_dir)
