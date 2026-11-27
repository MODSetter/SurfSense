"""A file one of the readers found, before its header says what it is."""

from dataclasses import dataclass
from pathlib import Path

from modules.llm.catalog.local.engines.llamacpp.elsewhere.places import App


@dataclass(frozen=True)
class Candidate:
    app: App
    # The file the runtime would open: the first part of a split build.
    path: Path
    # Every part of the weights, in order; just `path` for a single file.
    parts: tuple[Path, ...]
    # A projector the app itself recorded for this model (Ollama's manifest).
    projector: Path | None = None
    # What the app calls the model, when it calls it anything (an Ollama tag).
    name: str | None = None
    # Where the app says it came from: a repo, or the folders under the place.
    source: str | None = None
    # Files sharing a group are one repo's, so its projector goes with each
    # build, as it does in a searched repo. None where the app records pairing.
    group: Path | None = None
    # A split build with a part missing: the runtime would fail to open it.
    missing_parts: bool = False
