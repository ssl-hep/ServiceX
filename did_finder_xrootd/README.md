# ServiceX_DID_finder_XRootD
Find datasets by performing glob wildcarding via xrootd.

## Finding datasets

XRootD is a standard for remotely accessing HEP files, supported by many storage backends (EOS, dCache, etc.) This "DID finder" allows you to specify a glob wildcard pattern, such as
```
root://eospublic.cern.ch//eos/opendata/atlas/OutreachDatasets/2020-01-22/4lep/MC/*
```
to look up all the files matching this pattern and use those as input for a ServiceX transformation. In particular, files from CERN EOS are available via the gateways `eospublic.cern.ch`, `eosatlas.cern.ch`, `eoscms.cern.ch`, etc.

When accessing files from EOS, note that you must have the double slash `//` between the server name and the first element of the path!

