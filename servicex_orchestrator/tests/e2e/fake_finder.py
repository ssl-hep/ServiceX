"""A fake DID finder for the lookup e2e test, run through the real DIDFinderWorker.

Runs in the ServiceX_DID_Finder_lib poetry env (not the orchestrator's), so it
imports nothing from this repo. It PUTs files to the real app like any finder.

The DID says what to do: `e2e:<name>-<n_files>[-failonce]`. With `failonce` the
first lookup of a dataset fails halfway, after some batches are committed, so the
orchestrator retries it. Each call is appended to $E2E_STATE_DIR/lookups.log as
`<dataset_id> <did>`.

Env: TEMPORAL_ADDRESS, SERVICEX_INTERNAL_ENDPOINT, E2E_STATE_DIR.
"""

import os
import pathlib

from servicex_did_finder_lib.did_finder_worker import DIDFinderWorker

STATE = pathlib.Path(os.environ["E2E_STATE_DIR"])


def find_files(did, info, did_finder_args):
    dataset_id = info["dataset-id"]
    with open(STATE / "lookups.log", "a") as log:
        log.write(f"{dataset_id} {did}\n")
    name, n_files, *flags = did.split(":", 1)[1].split("-")
    n_files = int(n_files)
    failed_marker = STATE / f"failed-{dataset_id}"
    fail = "failonce" in flags and not failed_marker.exists()
    for i in range(n_files):
        if fail and i == n_files // 2:
            failed_marker.touch()
            raise RuntimeError("e2e: transient catalog error")
        yield {
            "paths": [f"root://e2e-se//{name}/file-{i}.root"],
            "adler32": "00000000",
            "file_size": 1000,
            "file_events": 10,
            "file_key": f"e2e:{name}-{i}",
        }


if __name__ == "__main__":
    # Small batches, so a failure halfway leaves committed files behind.
    DIDFinderWorker("rucio", find_files, batch_size=4, flush_interval=0.1).run()
