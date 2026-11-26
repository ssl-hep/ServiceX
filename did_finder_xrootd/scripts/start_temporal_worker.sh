#!/usr/bin/env bash
# Run the XRootD DID finder as a Temporal worker; the image's entrypoint.
# exec so the worker gets SIGTERM directly and drains in-flight lookups
exec /opt/servicex/.venv/bin/python -m servicex_did_finder_xrootd.temporal_worker
