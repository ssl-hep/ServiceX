"""A stand-in for ScienceContainerCommand that plays watch.sh's side of the socket."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from transformer_sidecar.science_container_command import ScienceContainerException


@dataclass
class Answer:
    """What the fake science container does with one replica."""

    status: str = "success."
    # Written to the requested output file; None writes nothing
    output: Optional[bytes] = b"data"
    log: str = "Transform stats: Total Events: 42, resulting file size 4"
    # Raise ScienceContainerException instead of answering
    broken: bool = False


class FakeScienceContainer:
    def __init__(self, request_path: Path, answers: list[Answer]):
        self.request_path = request_path
        self.answers = list(answers)
        self.requests: list[dict] = []
        self.confirmations = 0
        self.closed = False
        self._pending: Optional[Answer] = None

    def synch(self):
        if self.answers and self.answers[0].broken:
            raise ScienceContainerException("problem in getting GeT")

    def send(self, transform_request: dict):
        # The real one goes over a socket as JSON
        self.requests.append(json.loads(json.dumps(transform_request)))
        self._pending = self.answers.pop(0)

    def await_response(self) -> str:
        answer = self._pending
        self.request_path.mkdir(parents=True, exist_ok=True)
        (self.request_path / "abc.log").write_text(answer.log)
        if answer.output is not None:
            Path(self.requests[-1]["safeOutputFileName"]).write_bytes(answer.output)
        return answer.status

    def confirm(self):
        self.confirmations += 1

    def close(self):
        self.closed = True
