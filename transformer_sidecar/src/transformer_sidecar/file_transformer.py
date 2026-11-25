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
"""Transform one file: the core of the Temporal pilot's transform_file activity.

Plain Python, with no Temporal in it: pilot.py wraps it with heartbeats and turns the
outcome into the activity's result or error. It does what the Celery task in
transformer.py does, except that

- the output is named from the file's identity (file_key), not the replica read;
- it reports nothing to the app: the outcome goes back through Temporal;
- the science container always writes into the pod's scratch dir. The output is then
  uploaded to the object store, or copied into the output volume under a temporary
  name and renamed, so a reader of the volume never sees a partial file.
"""

import logging
import os
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from transformer_sidecar.object_store_manager import (
    ObjectStoreError,
    ObjectStoreManager,
)
from transformer_sidecar.science_container_command import ScienceContainerCommand
from transformer_sidecar.temporal_models import FileRef, output_object_name
from transformer_sidecar.transform_helpers import (
    convert_to_parquet,
    convert_to_rntuple,
    fill_stats_parser,
    get_process_info,
    order_replicas,
)
from transformer_sidecar.transformer_stats import TransformerStats

logger = logging.getLogger(__name__)

OBJECT_STORE_DEST = "object-store"
VOLUME_DEST = "volume"
SCIENCE_SUCCESS = "success."
# What the science container is asked for when the sidecar converts its output.
# Every transformer can write it.
ROOT_FILE = "root-file"


class PublishError(Exception):
    """The output was produced, but couldn't be written to its destination."""


@dataclass
class TransformOutcome:
    success: bool
    # The replica that was transformed; the first one tried when every one failed
    replica_used: str
    object_name: Optional[str] = None
    events: int = 0
    bytes: int = 0
    seconds: float = 0.0
    # From the science container's log, for the last replica tried
    error_info: str = ""
    log_body: str = ""


class FileTransformer:
    """Transforms files for one request, one at a time, through the science container.

    Built once per pilot. The lock keeps one file at a time on the science container:
    a canceled activity's thread may still be using it when the next file arrives.
    """

    def __init__(
        self,
        request_id: str,
        shared_dir: str,
        result_destination: str,
        result_format: str,
        capabilities: dict,
        science_container: ScienceContainerCommand,
        object_store: Optional[ObjectStoreManager] = None,
        output_dir: Optional[str] = None,
    ):
        if result_destination == OBJECT_STORE_DEST and object_store is None:
            raise ValueError("The object-store destination needs an ObjectStoreManager")
        if result_destination == VOLUME_DEST and not output_dir:
            raise ValueError("The volume destination needs an output dir")

        self.request_id = request_id
        self.result_destination = result_destination
        self.result_format = result_format
        self.capabilities = capabilities
        self.science_container = science_container
        self.object_store = object_store
        self.output_dir = Path(output_dir) if output_dir else None

        # If the user asked for a format the transformer can't write, it writes ROOT
        # and we convert it here.
        formats = capabilities.get("file-formats", [])
        self.convert_to_parquet = (
            result_format == "parquet" and "parquet" not in formats
        )
        self.convert_to_rntuple = (
            result_format == "root-rntuple" and "root-rntuple" not in formats
        )
        self.science_format = (
            ROOT_FILE
            if self.convert_to_parquet or self.convert_to_rntuple
            else result_format
        )

        # watch.sh writes the science log (abc.log) here
        self.request_path = Path(shared_dir, request_id)
        self.scratch_path = self.request_path / "scratch"
        self.scratch_path.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()

    def transform(self, file: FileRef) -> TransformOutcome:
        """Try the file's replicas in order until the science container succeeds.

        Raises ScienceContainerException if the science container is gone, and
        PublishError if the output couldn't be written to its destination.
        """
        with self._lock:
            return self._transform(file)

    def _transform(self, file: FileRef) -> TransformOutcome:
        log_extra = {"file_id": file.file_id}
        replicas = order_replicas(file.replicas)
        if not replicas:
            return TransformOutcome(
                success=False, replica_used="", error_info="The file has no replicas"
            )
        object_name = output_object_name(file.file_key, self.result_format)
        # The science container's output, before any conversion
        science_output = self.scratch_path / (
            Path(object_name).stem + ".root"
            if self.science_format == ROOT_FILE
            else object_name
        )

        logger.info(
            "Got transform request.",
            extra={**log_extra, "replicas": replicas, "object_name": object_name},
        )
        started = time.monotonic()
        start_process_info = get_process_info()
        stats = TransformerStats()

        try:
            for replica in replicas:
                logger.info(
                    "Trying to transform file",
                    extra={**log_extra, "input_path": replica},
                )
                science_output.unlink(missing_ok=True)
                status = self._run_science(file, replica, science_output)
                try:
                    stats = fill_stats_parser(
                        self.capabilities["stats-parser"], self.request_path / "abc.log"
                    )
                    if status != SCIENCE_SUCCESS:
                        continue
                    to_publish = self._converted(science_output)
                    if to_publish is None:
                        stats.error_info = (
                            "Sidecar format conversion failed"
                            if science_output.exists()
                            else "The transformer reported success but wrote no output"
                        )
                        continue
                    size = to_publish.stat().st_size
                    self._publish(to_publish, object_name)
                    logger.info(
                        "Transformed file",
                        extra={
                            **log_extra,
                            "input_path": replica,
                            "object_name": object_name,
                        },
                    )
                    return TransformOutcome(
                        success=True,
                        replica_used=replica,
                        object_name=object_name,
                        events=stats.total_events,
                        bytes=size,
                        seconds=time.monotonic() - started,
                    )
                finally:
                    # Exactly one confirmation per answer, or watch.sh stalls
                    self.science_container.confirm()
                    science_output.unlink(missing_ok=True)
        finally:
            self._log_process_times(start_process_info, log_extra)

        logger.error(
            f"Hard Failure: {stats.error_info}",
            extra={**log_extra, "input_path": replicas[0], "log_body": stats.log_body},
        )
        return TransformOutcome(
            success=False,
            replica_used=replicas[0],
            seconds=time.monotonic() - started,
            error_info=stats.error_info,
            log_body=stats.log_body,
        )

    def _run_science(self, file: FileRef, replica: str, output: Path) -> str:
        """Hand one replica to the science container and wait for its answer."""
        request = {
            "file-id": file.file_id,
            "request-id": self.request_id,
            "file-path": replica,
            "downloadPath": replica,
            "safeOutputFileName": output.as_posix(),
            "result-format": self.science_format,
        }
        self.science_container.synch()
        self.science_container.send(request)
        status = self.science_container.await_response()
        logger.info(
            f"Science container completed with status {status}",
            extra={"file_id": file.file_id},
        )
        return status

    def _converted(self, science_output: Path) -> Optional[Path]:
        """The file to publish: the science output, converted if need be. None if
        there is no output or the conversion failed."""
        if not science_output.exists():
            return None
        if self.convert_to_parquet:
            converted = convert_to_parquet(science_output)
        elif self.convert_to_rntuple:
            converted = convert_to_rntuple(science_output)
        else:
            return science_output
        if converted is not None:
            science_output.unlink()
        return converted

    def _publish(self, path: Path, object_name: str) -> None:
        """Write the output to its destination under object_name. Idempotent: a
        retry, on any replica, overwrites the same object."""
        try:
            if self.result_destination == VOLUME_DEST:
                self._publish_to_volume(path, object_name)
            else:
                t0 = time.time()
                # Deletes the local file, whatever happens
                self.object_store.upload_file(
                    self.request_id, object_name, path.as_posix()
                )
                logger.info(
                    "File uploaded to object store.",
                    extra={"object_name": object_name, "elapsed": time.time() - t0},
                )
        except ObjectStoreError as err:
            raise PublishError(str(err)) from err
        except OSError as err:
            raise PublishError(f"Could not write {object_name}: {err}") from err
        finally:
            path.unlink(missing_ok=True)

    def _publish_to_volume(self, path: Path, object_name: str) -> None:
        """Copy under a temporary name in the output dir, then rename: the rename is
        atomic on the volume, so nobody sees a partial file under the final name."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        partial = self.output_dir / f".{object_name}.{uuid.uuid4().hex}.partial"
        try:
            shutil.copyfile(path, partial)
            os.replace(partial, self.output_dir / object_name)
        finally:
            partial.unlink(missing_ok=True)

    @staticmethod
    def _log_process_times(start, log_extra) -> None:
        stop = get_process_info()
        logger.info(
            "File processed.",
            extra={
                **log_extra,
                "user": stop.user - start.user,
                "sys": stop.system - start.system,
                "iowait": stop.iowait - start.iowait,
            },
        )
