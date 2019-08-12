# ServiceX

ServiceX, a component of the IRIS-HEP DOMA group's iDDS, will be an
experiment-agnostic service to enable on-demand data delivery along the concepts
originally developed for ATLAS but specifically tailored for nearly-interactive,
high performance, array based and pythonic analyses context. It will provide
uniform backend interfaces to data storage services and  frontend
(client-facing) service endpoints for multiple different data formats and
organizational structures.  

It should be capable of retrieving and delivering
data from data lakes, as those systems and models evolve. It will depend on one
or more data management systems (eg. Rucio) to find and access the data. The
service will be capable of on-the-fly data transformations to enable data
delivery in a variety of different formats, including streams of ROOT data,
small ROOT files, HDF5, and Apache Arrow buffers as examples. In addition,
ServiceX will include pre-processing functionality for event data and
preparation for multiple clustering frameworks (e.g. such as Spark).  It will be
able to automatically unpack compressed formats, potentially including hardware
accelerated techniques, and can prefilter events so that only useful data is
transmitted to the user.

* [Documentation](https://ssl-hep.github.io/ServiceX/)
<!-- * [Kanban board](https://app.zenhub.com/workspaces/servicex-5caba4288d0ceb76ea94ae1f/board?repos=180217333) -->
* [Service frontend](https://servicex.slateci.net)
* [Service REST API](https://documenter.getpostman.com/view/7829270/SVYusJ4w?version=latest)