#!/usr/bin/env bash
set +e

# If transformer has already run then we don't need to compile
if [ ! -f /home/atlas/rel ]; then
  echo "Compile"
  bash /generated/runner.sh -c
  if [ $? != 0 ]; then
    echo "Compile step failed"
    exit 1
  fi
fi

echo "Transform a file $1 -> $2"
bash /generated/runner.sh -r -d "$1" -o "$2"
if [ $? != 0 ]; then
  echo "Transform step failed"
  exit 1
fi
