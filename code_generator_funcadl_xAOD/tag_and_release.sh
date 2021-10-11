#!/usr/bin/env bash
# This script will create a release branch and freeze the dependencies
git checkout develop
git pull --ff-only origin develop

git checkout -b v$1
docker build -t sslhep/servicex_code_gen_atlas_xaod:stage .
docker run --rm --entrypoint "pip" sslhep/servicex_code_gen_atlas_xaod:stage freeze > requirements.txt
docker rmi sslhep/servicex_code_gen_atlas_xaod:stage
git add requirements.txt
git commit -m "Freeze dependencies for V$1"
git push origin v$1
