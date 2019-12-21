# ServiceX_xAOD_CPP_transformer
ServiceX Transformer that converts ATLAS xAOD files into columnwise data

## Development
```bash
 python3 -m pip install -r requirements.txt
 python3 -m pip install --index-url https://test.pypi.org/simple/ --no-deps servicex
```

### Testing

#### Testing by running against known file and C++ files

Under tests you'll find input files needed to try this out. Use the following docker conmmand.

```
docker run --rm -it -v ${PWD}/tests/r21_test_cpp_files:/generated:ro -v ${PWD}/tests:/data:ro servicexxaodcpptransformer:latest python xAOD_CPP_Transformer.py --path /data/jets_10_events.root
```
