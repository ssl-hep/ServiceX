 # ServiceX - Data Delivery for the HEP Community

ServiceX is an on-demand data delivery service which strives to provide analysts working in high energy physics with the data they need in an easy, flexible, and highly performant manner.

## Features
- __Experiment-agnostic:__ Supports both the ATLAS and CMS collaborations.
- __Custom filters and pre-processing:__ Easily filter events, request specific columns, and unpack compressed formats using the [func-adl](https://github.com/iris-hep/func_adl) analysis description language.
- __Choose your format:__ ServiceX can deliver data in a variety of columnar formats, including streams of ROOT data, small ROOT files, HDF5, and Apache Arrow buffers.
- __No hassle:__ ServiceX uses Rucio to find and access data wherever it lives, so users don't have to worry about these details.
- __Simple and Pythonic:__ Using ServiceX takes only a few lines of code in any Python environment, such as a script  or Jupyter notebook.

## Getting Started

Check out our [installation guide](https://mweinberg2718.github.io/ServiceX_frontend/installation/) for instructions on how to obtain credentials and install the [ServiceX Python library](https://github.com/ssl-hep/ServiceX_frontend).

Once you've done that, refer to the documentation on how to get started [sending requests to ServiceX](https://mweinberg2718.github.io/ServiceX_frontend/requests/).

## Documentation

The full ServiceX docs can be found [here](https://mweinberg2718.github.io/ServiceX_frontend/).

## Self-Hosting

The [Scalable Systems Laboratory](https://iris-hep.org/ssl.html) (SSL) at IRIS-HEP maintains two instances of ServiceX: one to transform xAOD input files, and one to transform flat ntuples.

However, ServiceX is an open-source project, and you are welcome to host your own deployment. Instructions on how to configure and deploy ServiceX can be found in our [deployment guide](DEPLOYMENT.md).

## Contributing

The ServiceX team welcomes community contributions. If you'd like to get involved, please check out our [contributor guide](CONTRIBUTING.md).

## License

ServiceX is distributed under a [BSD 3-Clause License](LICENSE).

## Acknowledgements
![](https://iris-hep.org/assets/logos/Iris-hep-5-just-graphic.png)
![](https://iris-hep.org/assets/images/nsf-logo-128.png)

ServiceX is a component of the [IRIS-HEP](https://iris-hep.org/) Intelligent Data Delivery Service, and is supported by National Science Foundation under [Cooperative 
Agreement OAC-1836650](https://www.nsf.gov/awardsearch/showAward?AWD_ID=1836650). Any opinions, findings, conclusions or recommendations 
expressed in this material are those of the authors and do not necessarily 
reflect the views of the National Science Foundation.
