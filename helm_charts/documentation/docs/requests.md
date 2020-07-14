# Specifying a request

A transformation request is a specifically formatted request sent to ServiceX. It includes
information on what input dataset is to be used, what preselection is to be applied (including
computation of new columns, if any), and what columns should be returned to the user.

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
collection in some dataset:

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

For all but the simplest single-column requests, creating a Qastle query as input can be quite
cumbersome. ``func_adl`` provides additional libraries to construct queries. For example, we can
perform the same request using the ``func_adl_xAOD`` library:

    import func_adl_xAOD
    f_ds = func_adl_xAOD.ServiceXDatasetSource(ds)
    r = f_ds \
        .SelectMany('lambda e: e.Jets("AntiKt4EMTopoJets")') \
        .Select('lambda j: j.pt() / 1000.0') \
        .AsPandasDF('JetPt') \
        .value()
    print(r)

Note that this returns the output as a Pandas dataframe; the library also has ``AsROOTTTree()`` and
``AsAwkwardArray()`` methods to return the output has a flat TTree or an Awkward array.
