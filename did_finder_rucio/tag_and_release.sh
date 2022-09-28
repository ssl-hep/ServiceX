#!/usr/bin/env bash
# This script will create a release branch and freeze the dependencies
git checkout develop
git pull --ff-only origin develop

git checkout -b v$1
docker build -t sslhep/servicex-did-finder:stage .
docker run --rm --entrypoint "pip" sslhep/servicex-did-finder:stage freeze > requirements.txt
docker rmi sslhep/servicex-did-finder:stage
git add requirements.txt
git commit -m "Freeze dependencies for V$1"
git push origin v$1
