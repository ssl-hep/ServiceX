## Release x.x.x checklist
* [ ]  Merge PRs targeted for this milestone, and postpone any remaining issues/PRs to next milestone
* [ ]  Update change log
* [ ]  Create release branch in ServiceX and ServiceX_App repos
* [ ]  Freeze ServiceX chart dependencies in `servicex/requirements.yaml`
* [ ]  Freeze ServiceX_App dependencies in `setup.py`
* [ ]  Activate [ReadTheDocs version](https://readthedocs.org/projects/servicex/versions/) for the release branch
* [ ]  Update links to docs on release branch in ServiceX README and ServiceX_App website header and welcome emails
* [ ]  Make sure that DockerHub has tags for this release in sslhep/servicex_app and other image repos
* [ ]  Fix the default images and tags in `values.yaml` on release branch
* [ ]  Publish new version of ServiceX chart to ssl-hep/servicex helm repo
* [ ]  Make centrally-managed deployments to River cluster
* [ ]  Ensure docs on release branch are pointing to the correct deployments
* [ ]  Send announcement
