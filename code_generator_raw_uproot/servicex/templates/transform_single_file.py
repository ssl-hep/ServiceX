import os
import sys
import time
from pathlib import Path
import generated_transformer
import awkward as ak
import pyarrow.parquet as pq
import pyarrow
instance = os.environ.get('INSTANCE_NAME', 'Unknown')


def transform_single_file(file_path: str, output_path: Path, output_format: str):
    """
    Transform a single file and return some information about output
    :param file_path: path for file to process
    :param output_path: path to file
    :return: Tuple with (total_events: Int, output_size: Int)
    """
    try:
        stime = time.time()

        awkward_array_dict, histograms = generated_transformer.run_query(file_path)
        total_events = sum((ak.num(awkward_array[0], axis=0)
                            for awkward_array in awkward_array_dict.values()
                            if awkward_array[0] is not None), 0)

        ttime = time.time()

        if output_format == 'root-file':
            import uproot
            etime = time.time()
            # opening the file with open() is a workaround for a bug handling multiple colons
            # in the filename in uproot 5.3.9
            with open(output_path, 'b+w') as wfile:
                with uproot.recreate(wfile) as writer:
                    for k, v in awkward_array_dict.items():
                        if v[0] is not None and len(v[0]) > 0:
                            writer[k] = {field: v[0][field] for field in
                                         v[0].fields} if v[0].fields \
                                else v[0]
                        else:
                            writer.mktree(k, v[1])
                    for k, v in histograms.items():
                        writer[k] = v
            wtime = time.time()

        else:
            if histograms:
                raise RuntimeError("Cannot store histograms in a non-ROOT return file format")
            for treename, subarray in awkward_array_dict.items():
                subarray['treename'] = treename
            awkward_array = awkward_array_dict.popitem()[1]
            for treename, subarray in awkward_array_dict.items():
                awkward_array = ak.concatenate([awkward_array, subarray])

            arrow = ak.to_arrow_table(awkward_array)

            etime = time.time()

            try:
                writer = pq.ParquetWriter(output_path, arrow.schema)
            except pyarrow.lib.ArrowNotImplementedError:
                raise RuntimeError("Unable to translate output tables to parquet "
                                   "(probably different queries give different branches?)")
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
