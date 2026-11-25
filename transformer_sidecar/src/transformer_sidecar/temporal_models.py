# Copyright (c) 2026, IRIS-HEP
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
"""The transform_file activity's wire format.

These mirror the dataclasses of the same names in the orchestrator
(`servicex_orchestrator/models.py`), which schedules the activity from
FileBatchWorkflow. The sidecar doesn't import the orchestrator, so the two copies
must agree: Temporal sends them as JSON, and the field names are the contract.
"""

import hashlib
from dataclasses import dataclass
from typing import Optional

TRANSFORM_ACTIVITY_NAME = "transform_file"

# Error types the activity raises (plan §5.2). The orchestrator's retry policy lists
# FILE_FAILED and TRANSFORM_CODE_ERROR as non-retryable.
TRANSIENT_IO = "TransientIO"
FILE_FAILED = "FileFailed"
TRANSFORM_CODE_ERROR = "TransformCodeError"

FILE_SUCCESS = "success"


@dataclass
class TransformSpec:
    """What a transform worker needs to know about the request, besides the file."""

    request_id: str
    result_destination: str
    result_format: str


@dataclass
class FileRef:
    file_id: int
    file_key: str
    replicas: list[str]


@dataclass
class TransformFileInput:
    spec: TransformSpec
    file: FileRef


@dataclass
class FileResult:
    file_id: int
    status: str
    object_name: Optional[str] = None
    replica_used: Optional[str] = None
    events: int = 0
    bytes: int = 0
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    # Wall time the transform took
    transform_seconds: float = 0.0


def output_object_name(file_key: str, result_format: str) -> str:
    """The output object's name, from the file's identity rather than the replica that
    was read (plan §6.2), so every attempt on any replica writes the same object.

    Same rule as `output_object_name` in the orchestrator's `activities/stubs.py`.
    """
    suffix = ".parquet" if result_format == "parquet" else ".root"
    return hashlib.sha256(file_key.encode()).hexdigest()[:40] + suffix
