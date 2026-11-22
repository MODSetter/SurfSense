"""What one decode came to, as the child prints it on one line for its parent."""

import json
from dataclasses import asdict, dataclass
from typing import Literal

__all__ = ["DecodeOutcome", "OutcomeKind"]

# `no_room` and `no_audio` and `undecodable` would end the same way again.
OutcomeKind = Literal["decoded", "no_room", "no_audio", "undecodable"]


@dataclass(frozen=True)
class DecodeOutcome:
    kind: OutcomeKind
    # The decoded length, once decoded.
    seconds: float = 0.0
    # For `no_room`: what the decoded audio and its checkpoints take.
    needed_bytes: int = 0
    # For `undecodable`: the decoder's own words, for the log.
    detail: str = ""

    def line(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_line(cls, line: str) -> "DecodeOutcome":
        return cls(**json.loads(line))
