# ServiceX_Code_Generator_Python

This code generator takes python code/function and passes it unmodified for use by the transformer.

For instance, the following python function was saved in the file selection.py:

```
def transform_yt(ds):
    slc = ds.r[ds.domain_center[0], :, :].plot(("gas", "density"))
    sac = slc.frb[("gas", "density")].d
    return sac
```

The json passed to the transformer will need this function base64 encoded. To encode your python code:

```
cat selection.py | base64
```

Then in the json the "selection" key will take the base64-encoded string:
``` 
selection: "ZGVmIHRyYW5zZm9ybV95dChkcyk6CiAgICBzbGMgPSBkcy5yW2RzLmRvbWFpbl9jZW50ZXJbMF0sIDosIDpdLnBsb3QoKCJnYXMiLCAiZGVuc2l0eSIpKQogICAgc2FjID0gc2xjLmZyYlsoImdhcyIsICJkZW5zaXR5IildLmQKICAgIHJldHVybiBzYWMK"
```

Here is an example using the [ServiceX frontend](https://github.com/ssl-hep/ServiceX_frontend):

```
from servicex import ServiceXDataset
from servicex.servicex_python_function import ServiceXPythonFunction

def transform_yt(ds):
    slc = ds.r[ds.domain_center[0], :, :].plot(("gas", "density"))
    sac = slc.frb[("gas", "density")].d
    return sac

if __name__ == "__main__":
    dataset = "girder://579fb0aa7b6f0800011ea3b6#item"
    
    ds = ServiceXDataset(dataset, 
                         backend_name = "python"
    )
    selection = ServiceXPythonFunction(ds)
    encoded_selection = selection._encode_function(transform_yt)
    r = ds.get_data_pandas_df(encoded_selection)
    print(r)
```
