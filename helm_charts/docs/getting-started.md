# Prerequisites for users

Interacting with a central instance of ServiceX (as opposed to setting up your own instance)
consists in two parts: getting authenticated in the system by an administrator and installing the
appropriate client library.

## Getting authenticated

There are two instances of ServiceX, one to transform xAOD input files and one to transform flat
ntuples, and you must be separately authenticated to each in order to use them. You can go to the
[xAOD version](https://xaod.servicex.ssl-hep.org) or the
[Uproot version](https://uproot.servicex.ssl-hep.org) and put in the username and password
for your requested account. In addition, both instances rely on ATLAS credentials to access Rucio,
so you must be a member of the ATLAS VO to use them. The ServiceX admins will seek to personally
accept pending accounts, so once you've registered send a message to the admins (Ben Galewsky or
Marc Weinberg, e.g. via [Slack](https://iris-hep.slack.com/archives/CJH870SR2)) and they will
authorize any pending requests. Once you’re authenticated by an administrator your account will
have access to ServiceX, and you’ll be able to put in transform requests.

## Installing the client Python library

The documentation for the ServiceX client is shown
[here](https://pypi.org/project/servicex-cli/1.0.0rc3/). It's also useful to employ functions from the
func-adl libraries ([for xAOD](https://pypi.org/project/func-adl-xAOD/) or
[Uproot](https://pypi.org/project/func-adl-uproot/)). To interact with ServiceX via the client
library you’ll need an environment running Python 3.7:

    python -m pip install servicex==2.1
    python -m pip install func-adl-xAOD==1.1.0b5

In the Python prompt you can import the libraries and make a request using your registered username
and password.
