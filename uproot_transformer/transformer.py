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
import sys
import traceback

import awkward
import awkward1
import time

from servicex.transformer.servicex_adapter import ServiceXAdapter
from servicex.transformer.transformer_argument_parser import TransformerArgumentParser
from servicex.transformer.kafka_messaging import KafkaMessaging
from servicex.transformer.object_store_manager import ObjectStoreManager
from servicex.transformer.rabbit_mq_manager import RabbitMQManager
from servicex.transformer.uproot_events import UprootEvents
from servicex.transformer.uproot_transformer import UprootTransformer
from servicex.transformer.arrow_writer import ArrowWriter
import uproot
import os
import pyarrow.parquet as pq
import pandas as pd
import pyarrow as pa



# How many bytes does an average awkward array cell take up. This is just
# a rule of thumb to calculate chunksize
avg_cell_size = 42

messaging = None
object_store = None


class ArrowIterator:
    def __init__(self, arrow, chunk_size, file_path):
        self.arrow = arrow
        self.chunk_size = chunk_size
        self.file_path = file_path
        self.attr_name_list = ["not available"]

    def arrow_table(self):
        yield self.arrow


# noinspection PyUnusedLocal
def callback(channel, method, properties, body):
    transform_request = json.loads(body)
    _request_id = transform_request['request-id']
    _file_path = transform_request['file-path']
    _file_id = transform_request['file-id']
    _server_endpoint = transform_request['service-endpoint']
    _tree_name = transform_request['tree-name']
    # _chunks = transform_request['chunks']
    servicex = ServiceXAdapter(_server_endpoint)

    tick = time.time()
    try:
        # Do the transform
        servicex.post_status_update(file_id=_file_id,
                                    status_code="start",
                                    info="tree-name: "+_tree_name)

        root_file = _file_path.replace('/', ':')
        output_path = '/home/atlas/' + root_file
        transform_single_file(_file_path, output_path+".parquet", servicex, tree_name=_tree_name)

        tock = time.time()

        if object_store:
            object_store.upload_file(_request_id, root_file+".parquet", output_path+".parquet")
            os.remove(output_path+".parquet")

        servicex.post_status_update(file_id=_file_id,
                                    status_code="complete",
                                    info="Success")

        servicex.put_file_complete(_file_path, _file_id, "success",
                                   num_messages=0,
                                   total_time=round(tock - tick, 2),
                                   total_events=0,
                                   total_bytes=0)

    except Exception as error:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
        print(exc_value)

        transform_request['error'] = str(error)
        channel.basic_publish(exchange='transformation_failures',
                              routing_key=_request_id + '_errors',
                              body=json.dumps(transform_request))

        servicex.post_status_update(file_id=_file_id,
                                    status_code="failure",
                                    info="error: "+str(exc_value)[0:1024])

        servicex.put_file_complete(file_path=_file_path, file_id=_file_id,
                                   status='failure', num_messages=0, total_time=0,
                                   total_events=0, total_bytes=0)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def transform_single_file(file_path, output_path, servicex=None, tree_name='Events'):
    print("Transforming a single path: " + str(file_path))

    try:
        import generated_transformer
        start_transform = time.time()
        table = generated_transformer.run_query(file_path, tree_name)
        end_transform = time.time()
        print(f'generated_transformer.py: {round(end_transform - start_transform, 2)} sec')

        start_serialization = time.time()        
        table_awk1 = awkward1.from_awkward0(table)
        new_table = awkward1.to_awkward0(table_awk1)
        arrow = awkward.toarrow(new_table)
        end_serialization = time.time()
        print(f'awkward Table -> Arrow: {round(end_serialization - start_serialization, 2)} sec')

        if output_path:
            writer = pq.ParquetWriter(output_path, arrow.schema)
            writer.write_table(table=arrow)
            writer.close()

    except Exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
        print(exc_value)

        raise RuntimeError(
            "Failed to transform input file " + file_path + ": " + str(exc_value))

    if messaging:
        arrow_writer = ArrowWriter(file_format=args.result_format,
                                   object_store=None,
                                   messaging=messaging)

        #Todo implement chunk size parameter
        transformer = ArrowIterator(arrow, chunk_size=1000, file_path=file_path)
        arrow_writer.write_branches_to_arrow(transformer=transformer, topic_name=args.request_id,
                                             file_id=None, request_id=args.request_id)


def compile_code():
    import generated_transformer
    pass


if __name__ == "__main__":
    parser = TransformerArgumentParser(description="Uproot Transformer")
    args = parser.parse_args()

    print("-----", sys.path)
    kafka_brokers = TransformerArgumentParser.extract_kafka_brokers(args.brokerlist)

    print(args.result_destination, args.output_dir)
    if args.output_dir:
            messaging = None
            object_store = None
    elif args.result_destination == 'kafka':
        messaging = KafkaMessaging(kafka_brokers, args.max_message_size)
        object_store = None
    elif args.result_destination == 'object-store':
        messaging = None
        object_store = ObjectStoreManager()

    compile_code()

    if args.request_id and not args.path:
        rabbitmq = RabbitMQManager(args.rabbit_uri, args.request_id, callback)

    if args.path:
        print("Transform a single file ", args.path)
        transform_single_file(args.path, args.output_dir)
