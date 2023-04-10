import sys

from stream_unzip import stream_unzip
import httpx
import os


def zipped_chunks(input_path):
    # Iterable that yields the bytes of a zip file
    with httpx.stream('GET', input_path) as r:
        yield from r.iter_bytes(chunk_size=65536)


if __name__ == '__main__':
    input_path = sys.argv[1]
    output_path = sys.argv[2][:-2]
    print("Im running!")
    print("I/P", input_path)
    print("O/P", output_path)
    for file_name, file_size, unzipped_chunks in stream_unzip(zipped_chunks(input_path)):
        # unzipped_chunks must be iterated to completion or UnfinishedIterationError will be raised
        file_output_path = os.path.join(output_path, file_name.decode('utf-8'))
        with open(file_output_path, 'wb') as f:
            for chunk in unzipped_chunks:
                f.write(chunk)
