# Copyright (c) 2019-2025, IRIS-HEP
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

import os
import sys
import time
from pathlib import Path
from generated_transformer import run_query  # noqa
import awkward as ak
import pyarrow.parquet as pq
import functools
instance = os.environ.get('INSTANCE_NAME', 'Unknown')


def get_generator_timing(f):
    from time import perf_counter

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        t0 = perf_counter()
        for yv in f(*args, **kwargs):
            dt = perf_counter()-t0
            yield dt, yv
            t0 = perf_counter()
    return wrapper


def get_direct_timing(f):
    from time import perf_counter

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        t0 = perf_counter()
        rv = f(*args, **kwargs)
        dt = perf_counter()-t0
        return dt, rv
    return wrapper


def root_write_table_data(output_format, writer, outtreename, data):
    if output_format == 'root-file':
        if outtreename in writer:
            writer[outtreename].extend({field: data[field] for field in data.fields})
        else:
            writer[outtreename] = {field: data[field] for field in data.fields}
    else:  # RNTuple
        if outtreename in writer:
            writer[outtreename].extend(data)
        else:
            writer.mkrntuple(outtreename, data)


def transform_single_file(file_path: str, output_path: Path, output_format: str):
    """
    Transform a single file and return some information about output
    :param file_path: path for file to process
    :param output_path: path to file
    :return: Tuple with (total_events: Int, output_size: Int)
    """
    try:
        stime = time.time()
        total_events = 0
        ttimedt = 0
        etimedt = 0

        if output_format in ('root-file', 'root-rntuple'):
            import uproot
            # opening the file with open() is a workaround for a bug handling multiple colons
            # in the filename in uproot
            compression_algorithm = os.environ.get('COMPRESSION_ALGORITHM', 'ZSTD')
            compression_level = int(os.environ.get('COMPRESSION_LEVEL', 5))
            with open(output_path, 'b+w') as wfile:
                compression_obj = getattr(uproot, compression_algorithm)(compression_level)
                with uproot.recreate(wfile, compression=compression_obj) as writer:
                    for dt, item in get_generator_timing(run_query)(file_path):
                        ttimedt += dt
                        match item:
                            case ('tree', k, v):
                                total_events += ak.num(v, axis=0)
                                root_write_table_data(output_format, writer, k, v)
                            case ('obj', k, v):
                                writer[k] = v
            wtime = time.time()

        else:  # parquet
            awkward_array = None
            writer = None
            try:
                for dt, item in get_generator_timing(run_query)(file_path):
                    ttimedt += dt
                    match item:
                        case ('tree', k, awkward_array):
                            total_events += ak.num(awkward_array, axis=0)
                            awkward_array['treename'] = k
                            dt2, arrow = get_direct_timing(ak.to_arrow_table)(awkward_array)
                            etimedt += dt2
                            if not writer:
                                writer = pq.ParquetWriter(output_path, arrow.schema)
                            try:
                                writer.write_table(table=arrow)
                            except ValueError as e:
                                raise RuntimeError("Unable to translate output tables to parquet "
                                                   "(probably different queries give different "
                                                   f"branches?)\n{e}")
                        case ('obj', k, v):
                            raise RuntimeError("Cannot store histograms in a non-ROOT "
                                               "return file format")
            finally:
                if writer:
                    writer.close()
            wtime = time.time()

        output_size = os.stat(output_path).st_size
        print(f'Detailed transformer times. query_time:{round(ttimedt, 3)} '
              f'serialization: {round(etimedt, 3)} '
              f'writing: {round((wtime - stime) - etimedt - ttimedt, 3)}')

        print(f"Transform stats: Total Events: {total_events}, resulting file size {output_size}")
    except Exception as error:
        mesg = f"Failed to transform input file {file_path}: {error}"
        print(mesg)
        raise RuntimeError(mesg)

    return total_events, output_size


if __name__ == "__main__":
    transform_single_file(sys.argv[1], Path(sys.argv[2]), sys.argv[3])
