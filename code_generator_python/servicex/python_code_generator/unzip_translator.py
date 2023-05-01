def run_query(input_filenames=None, tree_name=None):
    from stream_unzip import stream_unzip
    import httpx

    def zipped_chunks(input_path):
        # Iterable that yields the bytes of a zip file
        with httpx.stream('GET', input_path) as r:
            yield from r.iter_bytes(chunk_size=65536)

    for file_name, file_size, unzipped_chunks in stream_unzip(zipped_chunks(input_filenames[0])):
        # unzipped_chunks must be iterated to completion or UnfinishedIterationError will be raised
        for chunk in unzipped_chunks:
            yield chunk, file_name
