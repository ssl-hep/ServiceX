#!/bin/bash

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

brew update && brew upgrade && brew install git-filter-repo

repo_list=(
    GIT_REMOTE_SERVICEX,
    GIT_REMOTE_SERVICEX_APP,
    GIT_REMOTE_SERVICEX_CODE_GENERATOR_FUNCADL_UPROOT,
)

folder_list=(
    "helm_charts",
    "servicex_app",
    "servicex_code_generator_funcadl_uproot",
    "servicex_code_generator_funcadl_xAOD",
    "servicex_code_generator_python",
    "servicex_did_finder_cernopendata",
    "servicex_did_finder_rucio",
    "servicex_uproot_transformer",
    "servicex_xaod_cpp_transformer"
)

branches_list=(
    "develop",
    "develop",
    "develop",
    "develop",
    "main",
    "develop",
    "develop",
    "develop",
    "develop"
)

migrated=()


for index in  [0.."${#repo_list[@]}"..1]
do
    git remote add -f "${folder_list[index]} ${repo_list[index]}"
    git merge "${folder_list[index]/${branches_list[index]}}" --allow-unrelated-histories
    git filter-repo --replace-refs delete-no-add --to-subdirectory-filter "${folder_list[index]}/"
    for repo in "${migrated[@]}"
    do
        git filter-repo --replace-refs delete-no-add --path-rename "${folder_list[index]}/${repo}":"${repo}"
    done
    migrated+=("${folder_list[index]}") 
done

git remote add origin "${GIT_TARGET}"
git push origin