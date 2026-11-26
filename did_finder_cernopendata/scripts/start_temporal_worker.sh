#!/usr/bin/env bash
# Run the CERN Open Data DID finder as a Temporal worker; the image's entrypoint.
# exec so the worker gets SIGTERM directly and drains in-flight lookups
exec /opt/servicex/.venv/bin/python -m did_finder_cernopendata.temporal_worker
