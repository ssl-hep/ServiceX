# ServiceX Example for ATLAS xAOD Files
These examples show how to use ServiceX to analyze events from ATLAS xAOD files.

## Prerequisites
These examples use a _coffea_ local processor to create histograms. 
This processor knows how to talk to a ServiceX instance and submit a request
in the func_adl analysis language.

To install:
```bash
pip install coffea[servicex]
```

## Obtain Credentials
Visit SSL's [xAOD ServiceX](https://xaod.servicex.ssl-hep.org) instance. Click 
on the _Sign-in_ button in the upper right hand corner. You will be asked to 
authenticate via GlobusAuth and complete a registration form. Once this form is
complete, it will be reviewed by SSL staff. You will receive an email upon 
approval. 

At this time you may return to the ServiceX page. Click on your name in the 
upper right hand corner and then select _Profile_ tab. Click on the download
button to have a servicex.yaml file generated with your access token and 
downloaded to your computer. 

![Download button](/docs/img/download-servicex-yaml.jpg)

You may place this in your home directory or within
the [servicex_frontend search path](https://github.com/ssl-hep/ServiceX_frontend#configuration).

