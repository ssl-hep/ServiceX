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

If you want to host your own notebook you'll need JupyterLab

```bash
pip install jupyterlab
```

The dynamic plots require the JupyterLab widgets

```bash
pip install jupyterlab-widgets
```

## Obtain Credentials

Visit SSL's [xAOD ServiceX](https://xaod.servicex.af.uchicago.edu) instance. Click
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

## Examples

<table>
<tr>
<td><a href="Z_ee.ipynb"><img src="/docs/img/Z_ee_example.jpg" alt="Z_ee Example Notebook"></a></td>
<td valign="center">Notebook to compute Mass of Z Boson from Z_ee</td>
</tr>
</table>
