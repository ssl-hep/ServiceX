import os
import sys
import time
from pathlib import Path
import inspect
import generated_transformer

instance = os.environ.get("INSTANCE_NAME", "Unknown")
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

        # We first see if the function takes two parameters; if so we assume the second
        # will be interpreted as the file name for the output.
        # If it doesn't, then we assume it's giving us back awkward array results

        provided_signature = inspect.signature(generated_transformer.run_query)
        if len(provided_signature.parameters) == 2:
            generated_transformer.run_query(file_path, str(output_path))
            if not output_path.exists():
                raise RuntimeError(
                    "Transformation did not produce expected output file "
                    f"{output_path}"
                )
            ttime = time.time()
            etime = time.time()
            wtime = time.time()
            total_events = 0
        else:
            import awkward as ak
            import uproot
            import pyarrow.parquet as pq
            import numpy as np

            output = generated_transformer.run_query(file_path)

            ttime = time.time()
            if output_format in ("root-file", "root-rntuple"):
                etime = time.time()
                if isinstance(output, ak.Array):
                    awkward_arrays = {default_tree_name: output}
                elif isinstance(output, dict):
                    awkward_arrays = output
                compression_algorithm = os.environ.get("COMPRESSION_ALGORITHM")
                compression_level = int(os.environ.get("COMPRESSION_LEVEL"))

                with open(output_path, "b+w") as wfile:
                    compression_obj = getattr(uproot, compression_algorithm)(
                        compression_level
                    )
                    with uproot.recreate(wfile, compression=compression_obj) as writer:
                        for key in awkward_arrays.keys():
                            total_events = awkward_arrays[key].__len__()
                            if output_format == "root-file":
                                if awkward_arrays[key].fields and total_events:
                                    o_dict = {
                                        field: awkward_arrays[key][field]
                                        for field in awkward_arrays[key].fields
                                    }
                                elif awkward_arrays[key].fields and not total_events:
                                    o_dict = {
                                        field: np.array([])
                                        for field in awkward_arrays[key].fields
                                    }
                                elif not awkward_arrays[key].fields and total_events:
                                    o_dict = {default_branch_name: awkward_arrays[key]}
                                else:
                                    o_dict = {default_branch_name: np.array([])}
                                writer.mktree(key, o_dict)
                            else:  # root-rntuple
                                writer.mkrntuple(key, awkward_arrays[key])

                wtime = time.time()
            elif output_format == "raw-file":
                etime = time.time()
                total_events = 0
                output_path = output
                wtime = time.time()
            else:
                if isinstance(output, dict):
                    tree_name = list(output.keys())[0]
                    awkward_array = output[tree_name]
                    print(
                        f"Returned type from your Python function is a dictionary - "
                        f"Only the first key {tree_name} will be written as parquet files. "
                        f"Please use root-file output to write all trees."
                    )
                else:
                    awkward_array = output

                total_events = ak.num(awkward_array, axis=0)
                arrow = ak.to_arrow_table(awkward_array)

                etime = time.time()

                writer = pq.ParquetWriter(output_path, arrow.schema)
                writer.write_table(table=arrow)
                writer.close()

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
