# Using ServiceX

A transformation request is a specifically formatted request sent to ServiceX. It includes
information on what input dataset is to be used, what preselection is to be applied (including
computation of new columns, if any), and what columns should be returned to the user.

## Selecting endpoints

Each request requires two endpoints, one corresponding to the service itself, and one for the
output of the request. The current available endpoints are shown below.

| Endpoint                           | Type     | Location  | Experiment | Input        |
|--------------------------------    |------    |-------    |--------    |----------    |
| rc1-xaod-servicex.uc.ssl-hep.org   | ServiceX | SSL-RIVER | ATLAS      | xAOD files   |
| rc1-xaod-minio.uc.ssl-hep.org      | MinIO    | SSL-RIVER | ATLAS      | xAOD files   |
| rc1-uproot-servicex.uc.ssl-hep.org | ServiceX | SSL-RIVER | ATLAS      | Flat ntuples |
| rc1-uproot-minio.uc.ssl-hep.org    | MinIO    | SSL-RIVER | ATLAS      | Flat ntuples |

## Creating a request via func_adl

In order to use ``func_adl`` directly we start with a [Qastle](https://github.com/iris-hep/qastle)
query as our input. The following is a query designed to extract the transverse momenta of a jet
collection in some xAOD-formatted dataset:

    my_query = "(call ResultTTree" \
        "(call Select" \
            "(call SelectMany" \
                "(call EventDataset (list 'localds:bogus'))" \
                "(lambda (list e) (call (attr e 'Jets') 'AntiKt4EMTopoJets'))" \
            ") (lambda (list j) (/ (call (attr j 'pt')) 1000.0))" \
        ") (list 'JetPt') 'analysis' 'junk.root')"

Given this input, we can produce output containing the transverse momenta of all jets in an ATLAS
xAOD file. We start by specifying the structure of the ServiceX request:

    import servicex
    dataset = ‘mc15_13TeV:mc15_13TeV.361106.PowhegPythia8EvtGen_AZNLOCTEQ6L1_Zee.merge.DAOD_STDM3.e3601_s2576_s2132_r6630_r6264_p2363_tid05630052_00’
    sx_endpoint = 'http://rc1-xaod-servicex.uc.ssl-hep.org'
    minio_endpoint = 'rc1-xaod-minio.uc.ssl-hep.org'
    ds = servicex.ServiceXDataset(
        dataset,
        servicex.ServiceXAdaptor(sx_endpoint, username='mweinberg', password='XXXXXXXXX'),
        servicex.MinioAdaptor(minio_endpoint)
        )

Once we have this, we can call ServiceX to output the results of our query in a convenient format:

    r = servicex.get_data_pandas_df(my_query)
    print(r)

After about 1--2 minutes, this prints a data frame with a single column for the transverse momenta.

A badly formatted query, or a problem with the file in the backend, will cause an exception to be
thrown. Note that there are also tools like the one
[here](https://github.com/mweinberg2718/useful-scripts/blob/master/xaod_qastle.py) that are capable
of turning a text file of requested columns (e.g.
[here](https://github.com/mweinberg2718/useful-scripts/blob/master/xaod_branches.txt)) into a
complete Qastle query.

## Using helper functions to construct a query

For all but the simplest single-column requests, creating a Qastle query as input can be quite
cumbersome. ``func_adl`` provides additional libraries to construct queries.

### Simple single-variable query

For example, we can perform the same request using the ``func_adl_xAOD`` library:

    import func_adl_xAOD
    f_ds = func_adl_xAOD.ServiceXDatasetSource(ds)
    r = f_ds \
        .SelectMany('lambda e: e.Jets("AntiKt4EMTopoJets")') \
        .Select('lambda j: j.pt() / 1000.0') \
        .AsPandasDF('JetPt') \
        .value()
    print(r)

Note that the ``Select()`` function transforms the input dataset by allowing you to select only
objects matching the selection criteria (in this case only the pT attribute of the jet collection).
Meanwhile the function ``SelectMany()`` shifts the hierarchy by returning a list of lists (in this
case a list of events, each containing a separate list of jets). ``AsPandasDF()`` formats the
output as a Pandas dataframe, and ``value()`` is responsible for executing the query.

### Multi-variable query

As a more realistic example, we can construct a request for the four-momenta of the Electron and
Muon collection. In this case let's output the results as a set of AwkwardArrays:

    r = f_ds \
        .Select('lambda e: (e.Electrons("Electrons"), e.Muons("Muons"))') \
        .Select('lambda ls: (ls[0].Select(lambda e: e.pt()), \
                             ls[0].Select(lambda e: e.eta()), \
                             ls[0].Select(lambda e: e.phi()), \
                             ls[0].Select(lambda e: e.e()), \
                             ls[1].Select(lambda m: m.pt()), \
                             ls[1].Select(lambda m: m.eta()), \
                             ls[1].Select(lambda m: m.phi()), \
                             ls[1].Select(lambda m: m.e()))') \
        .AsAwkwardArray(('ElePt', 'EleEta', 'ElePhi', 'EleE', 'MuPt', 'MuEta', 'MuPhi', 'MuE')) \
        .value()

Because the output is an AwkwardArray, which can handle the variable-size set of objects for each
event, it is no longer necessary to use the ``SelectMany()`` function as above.

### Query with applied filter

Next, let's consider the case where we wish to return information only for those jets with a pT
passing some threshold cut. This can be done via the ``Where()`` function:

    r = f_ds \
        .SelectMany('lambda e: e.Jets("AntiKt4EMTopoJets")') \
        .Where('lambda j: j.pt() / 1000.0 > 30.0') \
        .Select('lambda j: j.eta()') \
        .AsPandasDF('JetPt') \
        .value()

which returns a dataframe with the eta values of all jets whose pT is above 30 GeV.

### Complex query with filtering and a computed variable

Finally, let's take a complicated query where we ask for a computed variable (for simplicity we'll
use a nonsense variable like eta * phi) from the Electrons collection, but only for those events
with at least two jets with pT > 30 GeV. This can be done via:

    r = f_ds \
        .Where('lambda e: e.Jets("AntiKt4EMTopoJets") \
            .Where('lambda j: j.pt() / 1000.0 > 30.0').Count() >= 1') \
        .Select('lambda e: e.Electrons("Electrons")') \
        .Select('lambda e: e.Select(lambda ele: ele.eta() * ele.phi())') \
        .AsAwkwardArray('EleMyVar') \
        .value()

Note the nested ``Select()`` used to construct the computed variable; this ensures the variable is
only computed for electrons in the list of filtered events.

## Choosing the output

There are currently three choices for formatting the output of a ServiceX request: ``AsPandasDF``
returns the output as a Pandas
[dataframe](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html),
``AsROOTTree`` returns the output as a flat
[TTree](https://root.cern.ch/doc/master/classTTree.html), and ``AsAwkwardArray`` returns the output
as an [Awkward array](https://github.com/scikit-hep/awkward-array) suitable for use with
[uproot](https://github.com/scikit-hep/uproot).
