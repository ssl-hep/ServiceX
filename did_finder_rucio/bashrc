#!/bin/sh
# Authors:
# - Vincent Garonne, <vgaronne@gmail.com>, 2018

shopt -s checkwinsize

if [ ! -f /opt/rucio/etc/rucio.cfg ]; then
    echo "File rucio.cfg not found. It will generate one."
    mkdir -p /opt/rucio/etc/
    j2 rucio.cfg.j2 > /opt/rucio/etc/rucio.cfg
fi

echo "Enable shell completion on the rucio commands"
eval "$(register-python-argcomplete rucio)"
eval "$(register-python-argcomplete rucio-admin)"

export PYTHONPATH=/usr/src/app/did_finder
