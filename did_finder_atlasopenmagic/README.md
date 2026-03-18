# ServiceX_DID_finder_ATLASOpenMagic
 Access datasets for ServiceX with `atlasopenmagic`.

## Finding datasets

The ATLAS experiment hosts releases of [ATLAS Open Data](https://opendata.atlas.cern/). The proton-proton simulations and data are ROOT files, which come in two flavors: [education](https://opendata.atlas.cern/docs/category/data-for-education) and [research](https://opendata.atlas.cern/docs/category/data-for-research). The former are flat ROOT files with a limited set of branches, and the latter are in the PHYSLITE format which is also readable via `uproot` although with a more complicated schema (the `coffea` PHYSLITE schema is recommended for analysis). There are additional datasets for heavy ion collisions (also ROOT) and pure event generator output (in HEPMC format).

The [`atlasopenmagic`](https://github.com/atlas-outreach-data-tools/atlasopenmagic) package is provided as an interface to this data. To look up the files for a dataset, you must provide the _release_ for the dataset, as well as the _dataset ID_ (this is either a numeric string, corresponding to the ATLAS Monte Carlo simulation sample ID, or the string "data" for data). Optionally, where supported by the release, a _skim_ can be specifed. The `atlasopenmagic` DID finder accepts a single string encoding all these, which must be of the form `<release>/<dataset_id>` or `<release>/<dataset_id>/<skim>` where the appropriate replacements are made. The assumption is that the user will use `atlasopenmagic` directly in their code to handle the metadata aspects of using the ATLAS Open Data (e.g.\ sample cross sections, initial number of events, etc.) while using ServiceX to apply event selection and column reduction to the files.

Check the `helm/servicex/templates/did-finder-atlasopenmagic/deployment.yaml` file for an example of how to deploy this DID finder.
