#!/usr/bin/env bash
# Run the ServiceX DID finder as a Temporal worker; the image's entrypoint.
# exec so the worker gets SIGTERM directly and drains in-flight lookups
exec /opt/servicex/.venv/bin/python -m servicex_did_finder_servicex.temporal_worker
