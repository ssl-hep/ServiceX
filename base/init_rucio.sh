#!/bin/sh

shopt -s checkwinsize

echo "Enable shell completion on the rucio commands"
eval "$(register-python-argcomplete rucio)"
eval "$(register-python-argcomplete rucio-admin)"