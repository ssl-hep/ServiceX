import os
import sys
import time
from pathlib import Path
import generated_transformer
import awkward as ak
import pyarrow.parquet as pq
import uproot
import numpy as np
instance = os.environ.get('INSTANCE_NAME', 'Unknown')
default_tree_name = "servicex"
default_branch_name = "branch"


def transform_single_file(file_path: str, output_path: Path, output_format: str):
    """
    Transform a single file and return some information about output
    :param file_path: path for file to process
    :param output_path: path to file
    :return: Tuple with (total_events: Int, output_size: Int)
    """
    try:
        stime = time.time()

        output = generated_transformer.run_query(file_path)

        ttime = time.time()

        if output_format == 'root-file':
            etime = time.time()
            if isinstance(output, ak.Array):
                awkward_arrays = {default_tree_name: output}
            elif isinstance(output, dict):
                awkward_arrays = output
            with uproot.recreate(output_path) as writer:
                for key in awkward_arrays.keys():
                    total_events = awkward_arrays[key].__len__()
                    if awkward_arrays[key].fields and total_events:
                        o_dict = {field: awkward_arrays[key][field]
                                  for field in awkward_arrays[key].fields}
                    elif awkward_arrays[key].fields and not total_events:
                        o_dict = {field: np.array([])
                                  for field in awkward_arrays[key].fields}
                    elif not awkward_arrays[key].fields and total_events:
                        o_dict = {default_branch_name: awkward_arrays[key]}
                    else:
                        o_dict = {default_branch_name: np.array([])}
                    writer[key] = o_dict

            wtime = time.time()
        elif output_format == 'raw-file':
            etime = time.time()
            total_events = 0
            output_path = output
            wtime = time.time()
        else:
            if isinstance(output, dict):
                tree_name = list(output.keys()[0])
                awkward_array = output[tree_name]
                print(f'Returned type from your Python function is a dictionary - '
                      f'Only the first key {tree_name} will be written as parquet files. '
                      f'Please use root-file output to write all trees.')
            else:
                awkward_array = output
            explode_records = bool(awkward_array.fields)
            try:
                arrow = ak.to_arrow_table(awkward_array, explode_records=explode_records)
            except TypeError:
                arrow = ak.to_arrow_table(ak.repartition(awkward_array, None),
                                          explode_records=explode_records)

            etime = time.time()

            writer = pq.ParquetWriter(output_path, arrow.schema)
            writer.write_table(table=arrow)
            writer.close()

            wtime = time.time()

        output_size = os.stat(output_path).st_size
        print(f'Detailed transformer times. query_time:{round(ttime - stime, 3)} '
              f'serialization: {round(etime - ttime, 3)} '
              f'writing: {round(wtime - etime, 3)}')

        print(f"Transform stats: Total Events: {total_events}, resulting file size {output_size}")
    except Exception as error:
        mesg = f"Failed to transform input file {file_path}: {error}"
        print(mesg)
        raise RuntimeError(mesg)

    return total_events, output_size


if __name__ == "__main__":
    transform_single_file(sys.argv[1], Path(sys.argv[2]), sys.argv[3])
