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
