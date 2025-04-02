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

from transformer_sidecar.transformer_stats.uproot_stats import UprootStats


def test_uproot_stats():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as fp:
        test_logfile_path = Path(fp.name)
        fp.write("Transform stats: Total Events: 10000, resulting file size 102456'")
        fp.close()
        uproot_stats = UprootStats(test_logfile_path)
        assert uproot_stats.total_events == 10000
        assert uproot_stats.file_size == 102456
        assert uproot_stats.error_info == "Unable to determine error cause. Please consult log files"
        os.remove(test_logfile_path)


def test_bad_property():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as fp:
        test_logfile_path = Path(fp.name)
        fp.write("""
ValueError: key "lep_ptttt" does not exist (not in record)        
        """)
        fp.close()
        uproot_stats = UprootStats(test_logfile_path)
        assert uproot_stats.total_events == 0
        assert uproot_stats.file_size == 0
        assert uproot_stats.error_info == "Property naming error: lep_ptttt not available in dataset"
        os.remove(test_logfile_path)


def test_field_not_found():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as fp:
        test_logfile_path = Path(fp.name)
        fp.write("""
            raise FieldNotFoundError(
awkward.errors.FieldNotFoundError: no field 'AnalysisElectronsAuXXXxDyn.pt' in record with 1265 fields

This error occurred while attempting to slice
        """)
        fp.close()
        uproot_stats = UprootStats(test_logfile_path)
        assert uproot_stats.total_events == 0
        assert uproot_stats.file_size == 0
        assert uproot_stats.error_info == "Property naming error: AnalysisElectronsAuXXXxDyn.pt not available in dataset"
        os.remove(test_logfile_path)
