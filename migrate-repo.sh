#!/bin/bash

#
# Copyright (c) 2022 , IRIS-HEP
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#

GIT_TARGET="https://github.com/ssl-hep/ServiceX-monorepo.git"
GIT_REMOTE_SERVICEX="https://github.com/ssl-hep/ServiceX.git"
GIT_REMOTE_SERVICEX_APP="https://github.com/ssl-hep/ServiceX_App.git"
GIT_REMOTE_SERVICEX_CODE_GENERATOR_FUNCADL_UPROOT="https://github.com/ssl-hep/ServiceX_Code_Generator_FuncADL_uproot.git"
GIT_REMOTE_SERVICEX_CODE_GENERATOR_FUNCADL_xAOD="https://github.com/ssl-hep/ServiceX_Code_Generator_FuncADL_xAOD.git"
GIT_REMOTE_SERVICEX_CODE_GENERATOR_PYTHON="https://github.com/ssl-hep/ServiceX_Code_Generator_Python.git"
GIT_REMOTE_SERVICEX_DID_FINDER_CERNOPENDATA="https://github.com/ssl-hep/ServiceX_DID_Finder_CERNOpenData.git"
GIT_REMOTE_SERVICEX_DID_FINDER_RUCIO="https://github.com/ssl-hep/ServiceX_DID_Finder_Rucio.git"
GIT_REMOTE_SERVICEX_UPROOT_TRANSFORMER="https://github.com/ssl-hep/ServiceX_Uproot_Transformer.git"
GIT_REMOTE_SERVICEX_XAOD_CPP_TRANSFORMER="https://github.com/ssl-hep/ServiceX_xAOD_CPP_transformer.git"
GIT_REMOTE_SERVICEX_SIDECAR_TRANSFORMER="https://github.com/ssl-hep/ServiceX_Sidecar_Transformer.git"
GIT_REMOTE_X509_SECRETS="https://github.com/ssl-hep/X509_Secrets.git"

# brew update && brew upgrade && brew install git-filter-repo

repo_list=("${GIT_REMOTE_SERVICEX}" "${GIT_REMOTE_SERVICEX_APP}" "${GIT_REMOTE_SERVICEX_CODE_GENERATOR_FUNCADL_UPROOT}" "${GIT_REMOTE_SERVICEX_CODE_GENERATOR_FUNCADL_xAOD}" "${GIT_REMOTE_SERVICEX_CODE_GENERATOR_PYTHON}" "${GIT_REMOTE_SERVICEX_DID_FINDER_CERNOPENDATA}" "${GIT_REMOTE_SERVICEX_DID_FINDER_RUCIO}" "${GIT_REMOTE_SERVICEX_UPROOT_TRANSFORMER}" "${GIT_REMOTE_SERVICEX_XAOD_CPP_TRANSFORMER}" "${GIT_REMOTE_SERVICEX_SIDECAR_TRANSFORMER}" "${GIT_REMOTE_X509_SECRETS}")

folder_list=("helm" "servicex_app" "code_generator_funcadl_uproot" "code_generator_funcadl_xAOD" "code_generator_python" "did_finder_cernopendata" "did_finder_rucio" "uproot_transformer" "xaod_cpp_transformer" "transformer_sidecar" "x509_secrets")

branches_list=("develop" "develop" "develop" "develop" "main" "develop" "develop" "develop" "develop" "main" "develop")

migrated=()

for index in $(seq 0 $((${#repo_list[@]} - 1)));
do
    echo -e "\n${index} Iteration, ${folder_list[index]} Folder\n"
    git remote add -f "${folder_list[index]}" "${repo_list[index]}"
    git merge "${folder_list[index]}"/"${branches_list[index]}" -m "${folder_list[index]} Initial Merge" --allow-unrelated-histories
    git filter-repo --force --replace-refs delete-no-add --to-subdirectory-filter "${folder_list[index]}"/
    for repo in "${migrated[@]}"
    do
        git filter-repo --force --replace-refs delete-no-add --path-rename "${folder_list[index]}"/"${repo}":"${repo}"
    done
    migrated+=("${folder_list[index]}")
    echo -e "\nMigrated Folders: ${migrated[@]}\n\n"
done

git filter-repo --force --replace-refs delete-no-add --path-rename "${folder_list[0]}"/migrate.sh:migrate.sh
git commit -m "Mono repo Merge complete"
git remote add origin https://github.com/ssl-hep/ServiceX-monorepo.git
git push origin --force

# Now clean up the directory structure
git mv helm/docs .
git mv helm/examples .
git mv helm/.readthedocs.yml .
git mv helm/README.md .
git mv helm/CHANGELOG.md .
git mv helm/LICENSE .
git mv helm/mkdocs.yml .
mkdir .github
git mv helm/.github/ISSUE_TEMPLATE ./.github
git mv helm/.github/FUNDING.yml ./.github
git add .github
git rm helm/tag_and_release.sh
git rm servicex_app/tag_and_release.sh
git rm code_generator_funcadl_uproot/tag_and_release.sh
git rm code_generator_funcadl_xAOD/tag_and_release.sh
git rm did_finder_cernopendata/tag_and_release.sh
git rm did_finder_rucio/tag_and_release.sh
git rm uproot_transformer/tag_and_release.sh
git commit -m "Fixup directories after mono repo merge"
