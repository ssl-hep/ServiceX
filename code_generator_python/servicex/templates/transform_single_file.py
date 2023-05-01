import os
import sys
import time
from pathlib import Path
import generated_transformer
import awkward as ak
import pyarrow.parquet as pq
import uproot
instance = os.environ.get('INSTANCE_NAME', 'Unknown')
default_tree_name = "servicex"
codegen_type = os.environ.get('CODEGEN_TYPE', 'default')


def transform_single_file(file_path: str, output_path: Path, output_format: str):
    """
    Transform a single file and return some information about output
    :param file_path: path for file to process
    :param output_path: path to file
    :return: Tuple with (total_events: Int, output_size: Int)
    """
    try:
        stime = time.time()

        if codegen_type == 'default':
            awkward_array = generated_transformer.run_query(file_path)
            total_events = ak.num(awkward_array, axis=0)

            ttime = time.time()

            if output_format == 'root-file':
                etime = time.time()
                with uproot.recreate(output_path) as writer:
                    writer[default_tree_name] = {field: awkward_array[field] for field in
                                                 awkward_array.fields} if awkward_array.fields \
                        else awkward_array
                wtime = time.time()

            else:
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

            print(f"Transform stats: Total Events: {total_events}, \
                   resulting file size {output_size}")
        elif codegen_type == 'unzip':
            folder_output_path = os.path.dirname(output_path)
            for bytes, file_name in generated_transformer.run_query(file_path):
                file_output_path = os.path.join(folder_output_path, file_name.decode('utf-8'))
                print('File: ', file_output_path)
                with open(file_output_path, 'ab') as f:
                    f.write(bytes)
            total_events = 0
            output_size = os.stat(folder_output_path).st_size
        elif codegen_type == 'pandas':
            folder_output_path = os.path.dirname(output_path)
            pd_data = generated_transformer.run_query(file_path)
            pd_data.to_parquet(output_path)
            total_events = 0
            output_size = os.stat(folder_output_path).st_size
    except Exception as error:
        mesg = f"Failed to transform input file {file_path}: {error}"
        print(mesg)
        raise RuntimeError(mesg)

    return total_events, output_size


if __name__ == "__main__":
    transform_single_file(sys.argv[1], Path(sys.argv[2]), sys.argv[3])
