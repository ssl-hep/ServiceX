[![GitHub Actions Status](https://github.com/ssl-hep/ServiceX_Code_Generator_FuncADL_uproot/workflows/CI/CD/badge.svg)](https://github.com/ssl-hep/ServiceX_Code_Generator_FuncADL_uproot/actions)
[![Code Coverage](https://codecov.io/gh/ssl-hep/ServiceX_Code_Generator_FuncADL_uproot/graph/badge.svg)](https://codecov.io/gh/ssl-hep/ServiceX_Code_Generator_FuncADL_uproot)


ServiceX Code Generator
-----------------------
This microservice is a REST API that will generate python code for use in 
uproot-raw transformer. The query to extract the data is encoded in a JSON string.

Query Format
------------
The queries are JSON-encoded strings. The required structure is a list of "query dictionaries"; each query dictionary corresponds to an independent query to be done on the same file.

Each query dictionary must have a "treename" key. The value can be a string, a list of strings, or a dictionary mapping strings to strings. If it is a string, the tree of this name will be processed, and the result will be stored as a tree (or parquet equivalent) with the same name. If it is a list of strings, each of those trees will be processed with the same query, and each output will be stored in a tree of the corresponding name in the output. If "treename" is a dictionary, then each of the keys is treated as the name of an input tree, and the corresponding values are used as the output tree names (so multiple queries can be performed on the same input tree and written to different output trees).

The other key/value pairs in each query dictionary will be passed as keyword arguments to [uproot.arrays](https://uproot.readthedocs.io/en/latest/uproot.behaviors.TBranch.HasBranches.html#uproot-behaviors-tbranch-hasbranches-arrays) and allow the user to specify which branches to read and which cuts to apply.

An example illustrating these features:
```
        query = json.dumps([{'treename': 'sumWeights', 'filter_name': ['/totalE.*/']},
                            {'treename': ['nominal','JET_JER_EffectiveNP_1__1down'],
                             'filter_name': ['/mu_.*/', 'runNumber', 'lbn'],
                             'cut': 'met_met>150e3'},
                            {'treename': {'nominal': 'modified'},
                             'filter_name': ['lbn']},
                            ])
```

Usage
-----
This repo builds a container to be used in the `ServiceX` application. You can 
see the containers on docker hub.

Development
-----------
- Note that this service is tested on Python 3.10
- Use `pytest` to run the tests
- Use the `postman` template to send some sample queries to the service.


