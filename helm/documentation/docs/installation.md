# Getting started for users

This part is still a little sparse, as details are changing rapidly. Interacting with a central
instance of ServiceX (as opposed to setting up your own instance) consists in two parts: getting
authenticated in the system by an administrator and installing the appropriate frontend library.

## Getting authenticated

There are two instances of ServiceX, one to transform xAOD input files and one to transform flat
ntuples, and you must be separately authenticated to each in order to use them. You can go to the
[xAOD registration](http://rc1-xaod-servicex.uc.ssl-hep.org/) or the
[Uproot registration](http://rc1-uproot-servicex.uc.ssl-hep.org/) and put in the username and
password for your requested account. In addition, both instances rely on ATLAS credentials to
access Rucio, so you must be a member of the ATLAS VO to use them. In these early days the ServiceX
admins will seek to personally accept pending accounts, so once you've registered send a message to
the admins (Ben Galewsky or Marc Weinberg, e.g. via Slack) and they will authorize any pending
requests. Once you’re authenticated by an administrator your account will have access to ServiceX,
and you’ll be able to put in transform requests.

## Installing the frontend Python library

The documentation for the ServiceX frontend is shown
[here](https://pypi.org/project/servicex/1.0.0b3/). It's also useful to employ functions from the
func-adl libraries ([for xAOD](https://pypi.org/project/func-adl-xAOD/) or
[Uproot](https://pypi.org/project/func-adl-uproot/)). To interact with ServiceX via the frontend
library you’ll need an environment running Python 3.7 or later:

    python -m pip install servicex==2.0.0b6
    python -m pip install func-adl-xAOD==1.1.0b4

After the prompt you can import the libraries and make a request using your registered username and
password.
