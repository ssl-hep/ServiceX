#!/usr/bin/env bash

echo "Compile"
bash /generated/runner.sh -c

echo "Transform a file $1 -> $2"
bash /generated/runner.sh -r -d "$1" -o "$2"
