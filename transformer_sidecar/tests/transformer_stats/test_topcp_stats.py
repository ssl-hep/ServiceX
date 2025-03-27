# Copyright (c) 2025, IRIS-HEP
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

from transformer_sidecar.transformer_stats.topcp_stats import TopCPStats


def test_topcp_stats():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as fp:
        test_logfile_path = Path(fp.name)
        fp.write("Package.EventLoop        INFO    Processing events 0-68772 in file")
        fp.close()
        aod_stats = TopCPStats(test_logfile_path)
        assert aod_stats.total_events == 68772
        assert aod_stats.file_size == 0
        assert aod_stats.error_info == "Unable to determine error cause. Please consult log files"
        os.remove(test_logfile_path)

def test_error_capture():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as fp:
        test_logfile_path = Path(fp.name)
        fp.write("""
Py:CPAlgTextCfg      INFO Configuring AddConfigBlocks
>>> Configuring algorithms based on YAML file
Traceback (most recent call last):
  File "/TopCPToolkit/build/x86_64-el9-gcc13-opt/bin/runTop_el.py", line 260, in <module>
    run_job(sh, outputStreamName, "reco", args, flags)
  File "/TopCPToolkit/build/x86_64-el9-gcc13-opt/bin/runTop_el.py", line 162, in run_job
    algSeq = makeTextBasedSequence(
             ^^^^^^^^^^^^^^^^^^^^^^
  File "/TopCPToolkit/build/x86_64-el9-gcc13-opt/python/TopCPToolkit/commonAlgoConfig.py", line 186, in makeTextBasedSequence
    configSeq = config.configure()
                ^^^^^^^^^^^^^^^^^^
  File "/usr/AnalysisBase/25.2.45/InstallArea/x86_64-el9-gcc13-opt/python/AnalysisAlgorithmsConfig/ConfigText.py", line 208, in configure
    raise ValueError(f"Unkown block {blockName} in yaml file")
ValueError: Unkown block BPhyVerte in yaml file
Traceback (most recent call last):
  File "/TopCPToolkit/build/x86_64-el9-gcc13-opt/bin/runTop_el.py", line 254, in <module>
    check_output(outfile)
  File "/TopCPToolkit/build/x86_64-el9-gcc13-opt/bin/runTop_el.py", line 106, in check_output
    raise FileNotFoundError(
FileNotFoundError: The file '/tmp/out/data-ANALYSIS/output.root' was not successfully created, aborting.
        """)
        fp.close()
        topcp_stats = TopCPStats(test_logfile_path)
        assert topcp_stats.error_info == "ValueError: Unkown block BPhyVerte in yaml file"
        os.remove(test_logfile_path)