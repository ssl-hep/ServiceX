#!/usr/bin/env bash
set +e

echo "Compile"
bash /generated/runner.sh -c
if [ $? != 0 ]; then
  echo "Compile step failed"
  exit 1
fi

echo "Transform a file $1 -> $2"
bash /generated/runner.sh -r -d "$1" -o "$2"
if [ $? != 0 ]; then
  echo "Transform step failed"
  exit 1
fi
