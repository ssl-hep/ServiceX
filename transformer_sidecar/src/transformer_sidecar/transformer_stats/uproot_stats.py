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
from pathlib import Path
import re

from transformer_sidecar.transformer_stats import TransformerStats


class UprootStats(TransformerStats):
    def __init__(self, log_path: Path):
        super().__init__(log_path)

        matches = re.findall(
            r'Transform stats: Total Events: (\d+), resulting file size (\d+)',
            self.log_body)
        if len(matches) == 1:
            self.total_events, self.file_size = tuple(map(int, matches[0]))

        # Look for bad property names
        matches = re.findall(
            r'ValueError: key "([^"]*)" does not exist', self.log_body)

        if matches:
            self.error_info = f"Property naming error: {matches[0]} not available in dataset"

        matches = re.findall(
            r"awkward.errors.FieldNotFoundError: no field '([^\"]*)' in record.*", self.log_body)

        if matches:
            self.error_info = f"Property naming error: {matches[0]} not available in dataset"
