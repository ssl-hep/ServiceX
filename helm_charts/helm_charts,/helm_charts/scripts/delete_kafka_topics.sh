#!/usr/bin/env bash
for var in "$@"
do
    echo "Deleting $var"
    ./bin/kafka-topics.sh --bootstrap-server servicex-kafka-0.slateci.net:19092 --delete --topic $var
done

