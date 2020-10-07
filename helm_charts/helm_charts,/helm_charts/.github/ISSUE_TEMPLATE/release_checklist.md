## Release x.x.x checklist
* [ ]  Merge PRs targeted for this milestone, and postpone any remaining issues/PRs to next milestone
* [ ]  Update change log
* [ ]  Create release branch in all of the ServiceX repos
    - [ServiceX](https://github.com/ssl-hep/ServiceX)
    - [ServiceX_App](https://github.com/ssl-hep/ServiceX_App)
    - [X509_Secrets](https://github.com/ssl-hep/X509_Secrets)
    - [DID Finder](https://github.com/ssl-hep/ServiceX-DID-finder)
    - [xAOD_CPP Transformer](https://github.com/ssl-hep/ServiceX_xAOD_CPP_transformer)
    - [Uproot Transformer](https://github.com/ssl-hep/ServiceX_Uproot_Transformer)
    - [xAOD Code Generator](https://github.com/ssl-hep/ServiceX_Code_Generator_FuncADL_xAOD)
    - [Uproot Code Generator](https://github.com/ssl-hep/ServiceX_Code_Generator_FuncADL_uproot)
    - [ConfigMap Code Generator](https://github.com/ssl-hep/ServiceX_Code_Generator_Config_File)
* [ ]  Freeze ServiceX chart dependencies in `servicex/requirements.yaml`
* [ ]  Freeze ServiceX_App, and other service dependencies in `setup.py` or `requirements.txt`
* [ ]  Activate [ReadTheDocs version](https://readthedocs.org/projects/servicex/versions/) for the release branch
* [ ]  Update links to docs on release branch in ServiceX README and ServiceX_App website header and welcome emails
* [ ]  Make sure that DockerHub has tags for this release in sslhep/servicex_app and other image repos
* [ ]  Fix the default images and tags in `values.yaml` on release branch
* [ ]  Publish new version of ServiceX chart to ssl-hep/servicex helm repo
* [ ]  Make centrally-managed deployments to River cluster
* [ ]  Ensure docs on release branch are pointing to the correct deployments
* [ ]  Send announcement
