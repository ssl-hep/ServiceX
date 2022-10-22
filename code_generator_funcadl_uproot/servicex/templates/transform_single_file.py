import os
import sys
import time
from pathlib import Path
import generated_transformer
import awkward as ak
import pyarrow.parquet as pq

instance = os.environ.get('INSTANCE_NAME', 'Unknown')


def transform_single_file(file_path: str, output_path: Path):
    """
    Transform a single file and return some information about output
    :param file_path: path for file to process
    :param output_path: path to file
    :return: Tuple with (total_events: Int, output_size: Int)
    """
    total_events = 0
    output_size = 0
    try:
        stime = time.time()

        awkward_array = generated_transformer.run_query(file_path)
        total_events = ak.num(awkward_array, axis=0)

        ttime = time.time()

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
        output_size = os.stat(output_path).st_size

        wtime = time.time()

        print(f'Detailed transformer times. query_time:{round(ttime - stime, 3)} '
              f'serialization: {round(etime - ttime, 3)} '
              f'writing: {round(wtime - etime, 3)}')
    except Exception as error:
        mesg = f"Failed to transform input file {file_path}: {error}"
        print(mesg)
        raise RuntimeError(mesg)

    return total_events, output_size


if __name__ == "__main__":
    transform_single_file(sys.argv[1], Path(sys.argv[2]))
