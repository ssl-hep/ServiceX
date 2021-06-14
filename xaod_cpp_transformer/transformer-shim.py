#!/bin/python

# A python2 script that will run the transformer under python3.6 and setup the CMS
# environment along the way.

import os
import sys

cmd_line = 'python3.6 /servicex/transformer-actual.py ' + ' '.join(sys.argv[1:])
print cmd_line
print os.environ['PATH']
os.system(cmd_line)
