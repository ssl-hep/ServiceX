# Copyright (c) 2019-25, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
import importlib
import os
import sys
from unittest.mock import patch

import pytest

# finder.py builds Rucio clients and reads its configuration at import time, and
# every entrypoint imports it, so all of them are re-imported together.
FINDER_MODULES = (
    "rucio_did_finder.finder",
    "rucio_did_finder.celery",
    "rucio_did_finder.temporal_worker",
)

TEST_RSE_EXPRESSION = "cloud=CERN"
MINIMAL_ENV = {"RUCIO_RSE_EXPRESSION": TEST_RSE_EXPRESSION}


def _forget_finder_modules():
    for name in FINDER_MODULES:
        sys.modules.pop(name, None)


@pytest.fixture
def import_finder_module():
    """Import a finder module under a controlled environment.

    The shared finder module does all of its configuration at import time and
    builds live Rucio clients, so it is imported afresh for each test with those
    clients patched out and `os.environ` replaced by exactly what the test asks for.
    """

    def _import(module_name, **env):
        _forget_finder_modules()
        with patch("rucio.client.didclient.DIDClient"), patch(
            "rucio.client.replicaclient.ReplicaClient"
        ), patch.dict(os.environ, env, clear=True):
            return importlib.import_module(module_name)

    yield _import
    # Don't leave a module built from a synthetic environment behind for
    # anything else that imports it.
    _forget_finder_modules()
