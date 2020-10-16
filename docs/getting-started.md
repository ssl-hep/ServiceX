# ServiceX in 5 minutes

ServiceX is a data delivery service for high energy physicists.
It retrieves data from the grid and returns it in a columnar format.
It can also filter the data and perform computations.
ServiceX supports both the ATLAS and CMS collaborations on the LHC.

## Prerequisites
- Python 3.6+
- Member of the ATLAS or CMS collaborations

## Installation

ServiceX is accessed via a [Python client library](https://pypi.org/project/servicex/).
You can install it via:
```bash
pip install servicex==2.1b4
```

ServiceX also makes use of the [func-ADL]() analysis description language to specify requests.
To install it, run:
```bash
pip install func-adl-servicex
```

## Selecting an endpoint

Create a file called `.servicex` on your local machine in whichever directory your analysis code will be located. You can copy the template below:
```
api_endpoints:
  - endpoint: <your-endpoint>
    token: <api-token>
    type: (xaod | uproot)
```

To use the ServiceX client, you will need a ServiceX API token issued by a ServiceX backend instance.
Each ServiceX instance is dedicated to a specific experiment and file format.
You can use one of the centrally-managed instances of ServiceX running on the University of Chicago's River cluster:

| Endpoint                             | Type   | Input        |
|-----------------------------         |-----   |-------       |
| https://xaod.servicex.ssl-hep.org    | xaod   | xAOD files   |
| https://uproot.servicex.ssl-hep.org  | uproot | Flat ntuples |

Choose one of the above, and copy the URL into the `endpoint` field of your `.servicex` file. Set `type: xaod` or `type: uproot` to match your endpoint.

The remainder of this guide will use the xAOD instance.

## Obtaining credentials

Next, visit the URL in a browser and click the sign in button to create an account with that instance.
You can authenticate with the identity provider of your choice (e.g. CERN or your university). Save your profile.

On your new profile, you'll see an API token. Copy it using using the button on the right:

![Copying API token](img/copy-api-token.png)

Paste the token into your `.servicex` file, which should now look something like this:
```
api_endpoints:
  - endpoint: https://xaod.servicex.ssl-hep.org/
    token: <omitted>
    type: xaod
```

Since ServiceX instances rely on a shared grid certificate to access Rucio, each user must be approved by the ServiceX admins. They will be automatically notified, and you'll receive a welcome email once your account is approved.

## First request

Once you've been approved, you're ready to go!

You can interact with ServiceX by making a transformation request. A transformation request includes the following information:

- An input dataset
- Filters to be applied
- Computation of new columns (if any)
- Columns to be returned to the user

Here is a basic example which you can run to confirm that ServiceX is working for you (xAOD only):

```python
import servicex as sx
from func_adl_servicex import ServiceXDatasetSource

toy_dataset = "mc15_13TeV:mc15_13TeV.361106.PowhegPythia8EvtGen_AZNLOCTEQ6L1_Zee.merge.DAOD_STDM3.e3601_s2576_s2132_r6630_r6264_p2363_tid05630052_00"
ds = sx.ServiceXDataset(toy_dataset, "xaod")

df = ServiceXDatasetSource(ds) \
        .SelectMany('lambda e: e.Jets("AntiKt4EMTopoJets")') \
        .Select('lambda j: j.pt()/1000.0') \
        .AsPandasDF('JetPt') \
        .value()

print(df)
```

Expected output:
```
            JetPt
entry            
0       36.319766
1       34.331914
2       16.590844
3       11.389335
4        9.441805
...           ...
857133   6.211655
857134  47.653145
857135  32.738951
857136   6.260789
857137   5.394783

[11355980 rows x 1 columns]
```

## Next steps

Check out the [requests guide](requests.md) to learn more about specifying transformation requests using func-ADL.
