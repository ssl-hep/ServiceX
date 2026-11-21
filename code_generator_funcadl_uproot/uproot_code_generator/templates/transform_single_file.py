import os
import sys
import time
from pathlib import Path
import generated_transformer
import awkward as ak
import pyarrow as pa
import pyarrow.parquet as pq
import uproot

instance = os.environ.get("INSTANCE_NAME", "Unknown")
default_tree_name = "servicex"


def transform_single_file(file_path: str, output_path: Path, output_format: str):
    """
    Transform a single file and return some information about output
    :param file_path: path for file to process
    :param output_path: path to file
    :return: Tuple with (total_events: Int, output_size: Int)
    """
    try:
        stime = time.time()

        try:
            awkward_array = generated_transformer.run_query(file_path)
        except getattr(generated_transformer, "NoMatchingTreeError", ()):
            awkward_array = None
            missing_tree = True
        else:
            missing_tree = False
        total_events = 0 if missing_tree else ak.num(awkward_array, axis=0)

        ttime = time.time()

        if output_format in ("root-file", "root-rntuple"):
            etime = time.time()
            with open(output_path, "b+w") as wfile:
                with uproot.recreate(wfile) as writer:
                    if not missing_tree:
                        if output_format == "root-file":
                            writer.mktree(
                                default_tree_name,
                                {
                                    field: awkward_array[field]
                                    for field in awkward_array.fields
                                },
                            )
                        else:  # root-rntuple
                            writer.mkrntuple(default_tree_name, awkward_array)
            wtime = time.time()

        else:
            if missing_tree:
                etime = time.time()
                pq.write_table(pa.table({}), output_path)
            else:
                arrow = ak.to_arrow_table(awkward_array)
                etime = time.time()
                with pq.ParquetWriter(output_path, arrow.schema) as writer:
                    writer.write_table(table=arrow)
            wtime = time.time()

        output_size = os.stat(output_path).st_size
        print(
            f"Detailed transformer times. query_time:{round(ttime - stime, 3)} "
            f"serialization: {round(etime - ttime, 3)} "
            f"writing: {round(wtime - etime, 3)}"
        )

        print(
            f"Transform stats: Total Events: {total_events}, resulting file size {output_size}"
        )
    except Exception as error:
        mesg = f"Failed to transform input file {file_path}: {error}"
        print(mesg)
        raise RuntimeError(mesg)

    return total_events, output_size


if __name__ == "__main__":
    transform_single_file(sys.argv[1], Path(sys.argv[2]), sys.argv[3])
