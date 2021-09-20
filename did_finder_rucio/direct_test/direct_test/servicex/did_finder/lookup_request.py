from servicex.did_finder.rucio_adapter import RucioAdapter
from datetime import datetime


class LookupRequest:
    def __init__(self, did,
                 rucio_adapter: RucioAdapter, request_id):
        self.did = did
        self.prefix = 'prefix/'
        self.rucio_adapter = rucio_adapter
        self.request_id = request_id

    def lookup_files(self):
        """
        lookup files, add cache prefix if needed.
        """
        lookup_start = datetime.now()
        all_files = self.rucio_adapter.list_files_for_did(self.did)
        lookup_finish = datetime.now()

        ds_size = 0
        total_paths = 0
        avg_replicas = 0
        for af in all_files:
            ds_size += af['file_size']
            total_paths += len(af['file_path'])
            if self.prefix:
                af['file_path'] = [self.prefix+fp for fp in af['file_path']]
        if len(all_files):
            avg_replicas = float(total_paths)/len(all_files)
        print(
            f"Dataset contains {len(all_files)} files.",
            f"Lookup took {str(lookup_finish-lookup_start)}",
            {
                'requestId': self.request_id,
                'size': ds_size,
                'avg_replicas': avg_replicas
            })

        return all_files
