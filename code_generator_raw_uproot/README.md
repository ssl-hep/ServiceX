[![GitHub Actions Status](https://github.com/ssl-hep/ServiceX_Code_Generator_FuncADL_uproot/workflows/CI/CD/badge.svg)](https://github.com/ssl-hep/ServiceX_Code_Generator_FuncADL_uproot/actions)
[![Code Coverage](https://codecov.io/gh/ssl-hep/ServiceX_Code_Generator_FuncADL_uproot/graph/badge.svg)](https://codecov.io/gh/ssl-hep/ServiceX_Code_Generator_FuncADL_uproot)


ServiceX Code Generator
-----------------------
This microservice is a REST API that will generate python code for use in 
uproot-raw transformer. The query to extract the data is encoded in a JSON string.

Usage
-----
This repo builds a container to be used in the `ServiceX` application. You can 
see the containers on docker hub.

### Running the web service

The default is to run a web service that will take a `qastle` as input and 
return a binary zip file as output. To start that up, use the following 
docker command:

```
 docker run -it --rm -p 5000:5000  sslhep/servicex_code_gen_raw_uproot:latest
```

You can now make queries against port 5000.



Development
-----------
- Note that this service requires Python 3.7 or above
- Use `pytest` to run the tests
- Use the `postman` template to send some sample queries to the service.


