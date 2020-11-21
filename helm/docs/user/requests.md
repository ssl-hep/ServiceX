# Transformation Requests

A transformation request is a specifically formatted request sent to ServiceX.
It includes information on what input dataset is to be used, 
what preselection is to be applied (including computation of new columns, 
if any), and what columns should be returned to the user.

## Prerequisites

You must have installed the ServiceX client libraries and obtained credentials 
from a ServiceX backend with a file type matching your dataset.

If you have not yet completed these steps, refer to the 
[getting started guide](getting-started.md).

## Specifying requests with func-ADL

### Simple single-variable query

Considering the xAOD example of a basic request from the getting started guide, we can dig into what func-ADL is doing here:

```python
from func_adl_servicex import ServiceXSourceXAOD

ds = "mc15_13TeV:mc15_13TeV.361106.PowhegPythia8EvtGen_AZNLOCTEQ6L1_Zee.merge.DAOD_STDM3.e3601_s2576_s2132_r6630_r6264_p2363_tid05630052_00"

f_ds = ServiceXSourceXAOD(ds)
r = f_ds \
    .SelectMany('lambda e: e.Jets("AntiKt4EMTopoJets")') \
    .Select('lambda j: j.pt() / 1000.0') \
    .AsPandasDF('JetPt') \
    .value()
print(r)
```

Note that the ``Select()`` function transforms the input dataset by allowing you to select only
objects matching the selection criteria (in this case only the pT attribute of the jet collection).
Meanwhile the function ``SelectMany()`` shifts the hierarchy by returning a list of lists (in this
case a list of events, each containing a separate list of jets). ``AsPandasDF()`` formats the
output as a Pandas dataframe, and ``value()`` is responsible for executing the query.

### Multi-variable query

As a more realistic example, we can construct a request for the four-momenta of the Electron and
Muon collection. In this case let's output the results as a set of AwkwardArrays:

```python
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
```

Because the output is an AwkwardArray, which can handle the variable-size set of objects for each
event, it is no longer necessary to use the ``SelectMany()`` function as above.

### Query with applied filter

Next, let's consider the case where we wish to return information only for those jets with a pT
passing some threshold cut. This can be done via the ``Where()`` function:

```python
r = f_ds \
    .SelectMany('lambda e: e.Jets("AntiKt4EMTopoJets")') \
    .Where('lambda j: j.pt() / 1000.0 > 30.0') \
    .Select('lambda j: j.eta()') \
    .AsPandasDF('JetPt') \
    .value()
```

which returns a dataframe with the eta values of all jets whose pT is above 30 GeV.

### Complex query with filtering and a computed variable

Finally, let's take a complicated query where we ask for a computed variable (for simplicity we'll
use a nonsense variable like eta * phi) from the Electrons collection, but only for those events
with at least two jets with pT > 30 GeV. This can be done via:

```python
r = f_ds \
    .Where('lambda e: e.Jets("AntiKt4EMTopoJets") \
        .Where(lambda j: j.pt() / 1000.0 > 30.0).Count() >= 1') \
    .Select('lambda e: e.Electrons("Electrons")') \
    .Select('lambda e: e.Select(lambda ele: ele.eta() * ele.phi())') \
    .AsAwkwardArray('EleMyVar') \
    .value()
```

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
