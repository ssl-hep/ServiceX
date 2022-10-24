# Copyright (c) 2022, IRIS-HEP
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

# flake8: noqa

import os

from pathlib import Path

import tempfile

from transformer_sidecar.transformer_stats.aod_stats import AODStats


def test_aod_stats():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as fp:
        test_logfile_path = Path(fp.name)
        fp.write("Package.EventLoop        INFO    Processed 10000 events")
        fp.close()
        aod_stats = AODStats(test_logfile_path)
        assert aod_stats.total_events == 10000
        assert aod_stats.file_size == 0
        assert aod_stats.error_info == "Unable to determine error cause. Please consult log files"
        os.remove(test_logfile_path)


def test_bad_property():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as fp:
        test_logfile_path = Path(fp.name)
        fp.write("""
Building CXX object analysis/CMakeFiles/analysisLib.dir/Root/query.cxx.o
/home/atlas/rel/source/analysis/Root/query.cxx: In member function 'virtual StatusCode query::execute()':
/home/atlas/rel/source/analysis/Root/query.cxx:168:46: error: 'const class xAOD::Electron_v1' has no member named 'pttt'; did you mean 'pt'?
   _electrons_pt15.push_back((i_obj5->pttt()/1000.0));
                                      ^~~~
                                      pt
make[2]: *** [analysis/CMakeFiles/analysisLib.dir/Root/query.cxx.o] Error 1
make[1]: *** [analysis/CMakeFiles/analysisLib.dir/all] Error 2
make: *** [all] Error 2
        """)
        fp.close()
        aod_stats = AODStats(test_logfile_path)
        assert aod_stats.error_info == "Unable to determine error cause. Please consult log files"
        os.remove(test_logfile_path)
