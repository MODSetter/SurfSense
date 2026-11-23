"""What a row says about a model another app keeps: whose folder, which file,
and what its own header states."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FoundIn:
    # An `App` value: whose folder it is in.
    app: str
    # The file the runtime opens, shown so a person knows which one it is.
    path: str
    # What that app calls it or where it came from: an Ollama tag, a repo.
    source: str | None
    name: str
    architecture: str
    # Counted from the tensor table.
    parameters: int | None
    quantization: str
