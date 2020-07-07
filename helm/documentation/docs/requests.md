# Specifying a request

A transformation request is a specifically formatted request sent to ServiceX. It includes
information on what input dataset is to be used, what preselection is to be applied (including
computation of new columns, if any), and what columns should be returned to the user.

## Creating a request via func_adl

In order to use ``func_adl`` directly we start with a Qastle query as our input. We start from a
query designed to extract the four-momenta of the Electron collection in some dataset:

    my_query = "(Select data_column_source" \
        "(lambda (list Event)" \
            "(list (call (attr (attr Event 'Electrons') 'pt'))" \
                "(call (attr (attr Event 'Electrons') 'eta'))" \
                "(call (attr (attr Event 'Electrons') 'phi'))" \
                "(call (attr (attr Event 'Electrons') 'e')))))"

Given this input, we can produce a ``pandas.DataFrame`` containing the four momenta of all
electrons in an ATLAS xAOD file via

    import servicex
    dataset = ‘mc15_13TeV:mc15_13TeV.361106.PowhegPythia8EvtGen_AZNLOCTEQ6L1_Zee.merge.DAOD_STDM3.e3601_s2576_s2132_r6630_r6264_p2363_tid05630052_00’
    sx_endpoint = 'http://rc1-xaod-servicex.uc.ssl-hep.org'
    minio_endpoint = 'servicex-minio.uc.ssl-hep.org'
    ds = servicex.ServiceXDataset(
        dataset,
        servicex.ServiceXAdaptor(sx_endpoint, username='mweinberg', password='XXXXXXXXX'),
        servicex.MinioAdaptor(minio_endpoint)
        )
    r = servicex.get_data_pandas_df(my_query)
    print(r)

This queries ServiceX for the specified dataset, extracts the requested columns, and after about
1--2 minutes, prints a data frame with 4 columns (one for each of the variables).

A badly formatted query, or a problem with the file in the backend, will cause an exception to be
thrown. Note that there are also tools like the one
[here](https://github.com/mweinberg2718/useful-scripts/blob/master/xaod_qastle.py) that are capable
of turning a text file of requested columns (e.g.
[here](https://github.com/mweinberg2718/useful-scripts/blob/master/xaod_branches.txt)) into a
complete Qastle query.

For all but the simplest single-column requests, creating a Qastle query as input can be quite
cumbersome. ``func_adl`` provides additional libraries to construct queries. For example

    import func_adl_xAOD
    f_ds = func_adl_xAOD.ServiceXDatasetSource(ds)
    r = f_ds \
        .SelectMany('lambda e: e.Jets("AntiKt4EMTopoJets")') \
        .Select('lambda j: j.pt()/1000.0') \
        .AsPandasDF('JetPt') \
        .value()
    print(r)

## Creating a request via hep_tables

Another tool that can be used to make these requests is
[hep_tables](https://gordonwatts.github.io/hep_tables_docs/intro). This can (soon) be installed via
pip:

    pip install hep_tables

As a simple example of their use, we can make a plot of the electron transverse momenta. First we
set up the dataset and a computational graph for ``func_adl``:

    from hep_tables import xaod_table, make_local
    from func_adl import EventDataset
    import matplotlib.pyplot as plt

    dataset = EventDataset(‘localds://mc15_13TeV:mc15_13TeV.361106.PowhegPythia8EvtGen_AZNLOCTEQ6L1_Zee.merge.DAOD_STDM3.e3601_s2576_s2132_r6630_r6264_p2363_tid05630052_00')
    df = xaod_table(dataset)

Once we have this we can create a query for the electron transverse momenta and run it via
ServiceX:

    pts = df.Electrons(‘Electrons’).pt / 1000.0
    np_pts = make_local(pts)

This translates the query into the appropriate format for ServiceX, sends it to the service,
collects their results, and packages them locally as a JaggedArray. Finally we can make a plot from
this via:

    plt.hist(np_pts.flatten(), range=(0,100), bins=50)

Which results in a histogram of a transverse momentum distribution:

![hep_tables](img/hep_tables_example.png)

## Small example with filtering

Will include a small toy example with filtering here.
