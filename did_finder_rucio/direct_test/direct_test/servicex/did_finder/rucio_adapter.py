import xmltodict


class RucioAdapter:
    def __init__(self, replica_client):
        self.replica_client = replica_client

    @staticmethod
    def parse_did(did):
        """
        Parse a DID string into the scope and name
        Allow for no scope to be included
        :param did:
        :return: Dictionary with keys "scope" and "name"
        """
        d = dict()
        if ':' in did:
            d['scope'], d['name'] = did.split(":")
        else:
            d['scope'], d['name'] = '', did
        return d

    @staticmethod
    def get_paths(replicas):
        """
        extracts all the replica paths in a list sorted according
        to their priorities.
        """
        paths = [None] * len(replicas)
        for replica in replicas:
            paths[int(replica['@priority'], 10)-1] = replica['#text']
        return paths

    def list_files_for_did(self, did):
        """
        from rucio, gets list of file replicas in metalink xml,
        parses it, and returns a sorted list of all possible paths,
        together with checksum and filesize.
        """
        parsed_did = self.parse_did(did)
        reps = self.replica_client.list_replicas(
            [{'scope': parsed_did['scope'], 'name': parsed_did['name']}],
            schemes=['root'],
            metalink=True,
            sort='geoip'
        )
        g_files = []
        d = xmltodict.parse(reps)
        if 'file' in d['metalink']:
            for f in d['metalink']['file']:
                g_files.append(
                    {
                        'adler32': f['hash']['#text'],
                        'file_size': int(f['size'], 10),
                        'file_events': 0,
                        'file_path': self.get_paths(f['url'])
                    }
                )
        return g_files
