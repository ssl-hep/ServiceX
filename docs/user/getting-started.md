# ServiceX in 5 minutes

ServiceX is a data delivery service for high energy physicists working on the ATLAS and CMS collaborations on the LHC. It retrieves data from the grid, applies any desired transformations (such as filters or computations), and returns it in a columnar format.
Requests to ServiceX can be made in Python using the [func-ADL](https://pypi.org/project/func-adl-servicex/1.0/) analysis description language or TCut selection strings.

## Prerequisites
- Python 3.6, 3.7, or 3.8
- Member of the ATLAS or CMS collaborations

## Installation

```bash
pip install servicex-clients
```

This is an umbrella package which includes all of the frontend client 
libraries used to communicate with a ServiceX backend. 
There are multiple ways to specify a request, but we will use 
func-ADL in this tutorial.

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

| Endpoint                                   | Collaboration | Type   | Input        |
|-----------------------------               |------         |-----   |-------       |
| https://xaod.servicex.ssl-hep.org          | ATLAS         | xaod   | xAOD files   |
| https://uproot-atlas.servicex.ssl-hep.org  | ATLAS         | uproot | Flat ntuples |
| https://uproot-cms.servicex.ssl-hep.org    | CMS           | uproot | Flat ntuples |


Choose one of the above, and copy the URL into the `endpoint` field of your `.servicex` file. Set `type: xaod` or `type: uproot` to match your endpoint.

The remainder of this guide will use the xAOD instance.

## Obtaining credentials

Next, visit the URL in a browser and click the sign in button to create an account with that instance.
You can authenticate with the identity provider of your choice (e.g. CERN or your university). Save your profile.

On your new profile, you'll see an API token. Copy it using using the button on the right:

![Copying API token](../img/copy-api-token.png)

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

Below are some basic examples which you can run to confirm that ServiceX is working for you.

### xAOD

```python
from func_adl_servicex import ServiceXSourceXAOD

dataset_name = "mc15_13TeV:mc15_13TeV.361106.PowhegPythia8EvtGen_AZNLOCTEQ6L1_Zee.merge.DAOD_STDM3.e3601_s2576_s2132_r6630_r6264_p2363_tid05630052_00"
src = ServiceXSourceXAOD(dataset_name)
df = src \
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

### Uproot

```python
import pandas as pd
from func_adl_servicex import ServiceXSourceUpROOT

dataset_name = "data15_13TeV:data15_13TeV.00282784.physics_Main.deriv.DAOD_PHYSLITE.r9264_p3083_p4165_tid21568807_00"
src = ServiceXSourceUpROOT(dataset_name, "CollectionTree")
data = src.Select("lambda e: {'JetPT': e['AnalysisJetsAuxDyn.pt']}") \
    .AsParquetFiles('junk.parquet') \
    .value()
df = pd.read_parquet(data[0])
print(df)
```

Expected output:
```
                                                   JetPT
0      [56970.56, 57738.047, 24149.762, 15421.779, 14...
1      [123299.94, 89595.32, 75777.94, 18421.592, 164...
2      [172519.64, 115030.47, 111144.8, 97817.69, 934...
3      [28965.395, 15481.423, 14233.97, 16032.507, 12...
4      [288785.3, 189529.4, 80025.805, 43544.61, 1581...
...                                                  ...
54238  [347737.28, 313428.75, 46344.66, 33925.395, 20...
54239                   [45954.137, 41864.71, 15005.428]
54240  [76411.27, 66487.41, 60403.04, 51341.3, 41749....
54241                  [33027.637, 24204.908, 18219.818]
54242                                                 []

[54243 rows x 1 columns]
```

## Next steps

Check out the [requests guide](requests.md) to learn more about specifying transformation requests using func-ADL.
