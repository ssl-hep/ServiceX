import os
import sys
import time
from pathlib import Path
import generated_transformer
import awkward as ak
import pyarrow.parquet as pq
import uproot

instance = os.environ.get("INSTANCE_NAME", "Unknown")
default_tree_name = "servicex"


def root_write_table_data(output_format, writer, outtreename, data):
    if output_format == "root-file":
        tree_data = {field: data[field] for field in data.fields}
        if outtreename in writer:
            writer[outtreename].extend(tree_data)
        else:
            writer.mktree(outtreename, tree_data)
    else:  # root-rntuple
        if outtreename in writer:
            writer[outtreename].extend(data)
        else:
            writer.mkrntuple(outtreename, data)


def parquet_write_table_data(output_path, awkward_array):
    arrow = ak.to_arrow_table(awkward_array)
    writer = pq.ParquetWriter(output_path, arrow.schema)
    try:
        writer.write_table(table=arrow)
    finally:
        writer.close()


def transform_single_file(file_path: str, output_path: Path, output_format: str):
    """
    Transform a single file and return some information about output
    :param file_path: path for file to process
    :param output_path: path to file
    :return: Tuple with (total_events: Int, output_size: Int)
    """
    try:
        stime = time.time()

        awkward_array = generated_transformer.run_query(file_path)
        total_events = ak.num(awkward_array, axis=0)

        ttime = time.time()

        if output_format in ("root-file", "root-rntuple"):
            etime = time.time()
            with open(output_path, "b+w") as wfile:
                with uproot.recreate(wfile) as writer:
                    root_write_table_data(
                        output_format, writer, default_tree_name, awkward_array
                    )
            wtime = time.time()

        elif output_format == "parquet":
            etime = time.time()
            parquet_write_table_data(output_path, awkward_array)
            wtime = time.time()
        else:
            raise RuntimeError(f"Unsupported output format '{output_format}'")

        output_size = os.stat(output_path).st_size
        print(
            f"Detailed transformer times. query_time:{round(ttime - stime, 3)} "
            f"serialization: {round(etime - ttime, 3)} "
            f"writing: {round(wtime - etime, 3)}"
        )

        print(
            f"Transform stats: Total Events: {total_events}, "
            f"resulting file size {output_size}"
        )
    except Exception as error:
        mesg = f"Failed to transform input file {file_path}: {error}"
        print(mesg)
        raise RuntimeError(mesg)

    return total_events, output_size


if __name__ == "__main__":
    transform_single_file(sys.argv[1], Path(sys.argv[2]), sys.argv[3])
