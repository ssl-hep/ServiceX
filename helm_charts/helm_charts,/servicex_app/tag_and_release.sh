#!/usr/bin/env bash
# This script will create a release branch and freeze the dependencies
git checkout develop
git pull --ff-only origin develop

git checkout -b v$1
docker build -t sslhep/servicex_app:stage .
docker run --rm --entrypoint "pip" sslhep/servicex_app:stage freeze > requirements.txt
docker rmi sslhep/servicex_app:stage
git add requirements.txt

sed s"/version='.*'/version='$1'/" setup.py > new_setup.py
mv new_setup.py setup.py
git add setup.py

git commit -m "Freeze dependencies for V$1"
git push origin v$1
