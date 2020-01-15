# ServiceX_xAOD_CPP_transformer

![](https://github.com/ssl-hep/ServiceX_xAOD_CPP_transformer/workflows/Docker%20Hub/badge.svg)

ServiceX Transformer that converts ATLAS xAOD files into columnwise data

## Usage

You can invoke the transformer from the command line. For example:

```
> docker run --rm -it sslhep/servicex_xaod_cpp_transformer:latest python transformer.py --help
usage: transformer.py [-h] [--brokerlist BROKERLIST] [--topic TOPIC]
                      [--chunks CHUNKS] [--tree TREE] [--attrs ATTR_NAMES]
                      [--path PATH] [--limit LIMIT]
                      [--result-destination {kafka,object-store,output-dir}]
                      [--output-dir OUTPUT_DIR]
                      [--result-format {arrow,parquet,root-file}]
                      [--max-message-size MAX_MESSAGE_SIZE]
                      [--rabbit-uri RABBIT_URI] [--request-id REQUEST_ID]

xAOD CPP Transformer

optional arguments:
  -h, --help            show this help message and exit
  --brokerlist BROKERLIST
                        List of Kafka broker to connect to
  --topic TOPIC         Kafka topic to publish arrays to
  --chunks CHUNKS       Arrow Buffer Chunksize
  --tree TREE           Tree from which columns will be inspected
  --attrs ATTR_NAMES    List of attributes to extract
  --path PATH           Path to single Root file to transform
  --limit LIMIT         Max number of events to process
  --result-destination {kafka,object-store,output-dir}
                        kafka, object-store
  --output-dir OUTPUT_DIR
                        Local directory to output results
  --result-format {arrow,parquet,root-file}
                        arrow, parquet, root-file
  --max-message-size MAX_MESSAGE_SIZE
                        Max message size in megabytes
  --rabbit-uri RABBIT_URI
  --request-id REQUEST_ID
                        Request ID to read from queue
```

You will need an X509 proxy avaiable as a mountable volume. The X509 Secret
container can do using your credentials and cert:
```bash
docker run --rm \
    --mount type=bind,source=$HOME/.globus,readonly,target=/etc/grid-certs \
    --mount type=bind,source="$(pwd)"/secrets/secrets.txt,target=/servicex/secrets.txt \
    --mount type=volume,source=x509,target=/etc/grid-security \
    --name=x509-secrets sslhep/x509-secrets:latest
```


## Development
```bash
 python3 -m pip install -r requirements.txt
 python3 -m pip install --index-url https://test.pypi.org/simple/ --no-deps servicex
```

### Testing

#### Testing by running against known file and C++ files

Under tests you'll find input files needed to try this out. Use the following docker conmmand.

```
docker run --rm -it \
  --mount type=volume,source=x509,target=/etc/grid-security-ro \
  --mount type=bind,source=$(pwd),target=/code \
  --mount type=bind,source=$(pwd)/tests,target=/data \
  --mount type=bind,source=$(pwd)/tests/r21_test_cpp_files,target=/generated,readonly \
  sslhep/servicex_xaod_cpp_transformer:latest bash
```

Then use `trasformer.py` and pass it the `--path` argument.

For example:
```bash
 python transformer.py --path /data/jets_10_events.root --result-format root-file --output-dir /tmp --result-destination output-dir
```