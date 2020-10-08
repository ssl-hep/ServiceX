---
name: Release Checklist
about: List of tasks to be completed during each release
title: ''
labels: ''
assignees: ''

---

## Release x.x.x checklist
* [ ]  Merge PRs targeted for this milestone, and postpone any remaining issues/PRs to next milestone
* [ ]  Update change log
* [ ]  Create release branch in [ServiceX](https://github.com/ssl-hep/ServiceX) repo and freeze chart dependencies in `servicex/requirements.yaml`
* [ ]  Perform `helm dependency update serviceX` to update `requirements.lock`
* [ ]  Create release branch in each service repo and freeze dependencies in `setup.py` or `requirements.txt`:
  * [ ] [ServiceX_App](https://github.com/ssl-hep/ServiceX_App)
  * [ ] [X509_Secrets](https://github.com/ssl-hep/X509_Secrets)
  * [ ] [DID Finder](https://github.com/ssl-hep/ServiceX-DID-finder)
  * [ ] [xAOD_CPP Transformer](https://github.com/ssl-hep/ServiceX_xAOD_CPP_transformer)
  * [ ] [Uproot Transformer](https://github.com/ssl-hep/ServiceX_Uproot_Transformer)
  * [ ] [xAOD Code Generator](https://github.com/ssl-hep/ServiceX_Code_Generator_FuncADL_xAOD)
  * [ ] [Uproot Code Generator](https://github.com/ssl-hep/ServiceX_Code_Generator_FuncADL_uproot)
  * [ ] [ConfigMap Code Generator](https://github.com/ssl-hep/ServiceX_Code_Generator_Config_File)
* [ ]  Activate [ReadTheDocs version](https://readthedocs.org/projects/servicex/versions/) for the release branch
* [ ]  Update links to docs in README on release branch
* [ ]  Set chart version and app version in `servicex/Chart.yaml`
    - Note that the version must match the release branch name. Do not include the leading "v" and RC should be lowercase. 
      Verify the settings with `helm template serviceX | grep URL` and insure the link works.
* [ ]  Make sure that DockerHub has tags for this release in sslhep/servicex_app and other image repos
* [ ]  Fix the default images and tags in `servicex/values.yaml` on release branch
* [ ]  Publish new version of ServiceX chart to ssl-hep/servicex helm repo
* [ ]  Make centrally-managed deployments to River cluster
* [ ]  Ensure docs on release branch are pointing to the correct deployments
* [ ]  Send announcement
