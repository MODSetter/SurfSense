"""What each install put on disk, written when it lands.

A vision build is weights and a projector, and the pairing is decided once, at
install, from the build that was downloaded. Reading it back from names later
paired a lone projector with whatever model sat beside it, text models included,
and a second vision model's `mmproj-F16.gguf` overwrote the first one's.
"""

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

RECORD_FILE = "installs.json"


def projector_filename(model_id: str) -> str:
    """Where a model's projector is saved: its own name, so two vision models
    never share or overwrite one, and a file copied by hand under this name is
    paired the same way."""
    return f"mmproj-{model_id}.gguf"


@dataclass(frozen=True)
class InstalledBuild:
    """One installed build. `model_id` is the runtime's name for it: the first
    weights file without `.gguf`."""

    model_id: str
    repo: str
    revision: str
    quantization: str
    weights: tuple[str, ...]
    projector: str | None = None
    projector_gguf: Mapping[str, Any] = field(default_factory=dict)

    @property
    def files(self) -> tuple[str, ...]:
        return self.weights + ((self.projector,) if self.projector else ())


def read_installs(models_dir: Path) -> dict[str, InstalledBuild]:
    path = models_dir / RECORD_FILE
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    installs = {}
    for item in raw.get("builds", []):
        try:
            item["weights"] = tuple(item["weights"])
            build = InstalledBuild(**item)
        except (KeyError, TypeError):
            continue
        installs[build.model_id] = build
    return installs


def write_installs(models_dir: Path, installs: Mapping[str, InstalledBuild]) -> None:
    """Replaced atomically, so a half-written record never pairs anything."""
    models_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "builds": [
            _plain(b) for b in sorted(installs.values(), key=lambda b: b.model_id)
        ]
    }
    temporary = models_dir / f"{RECORD_FILE}.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(models_dir / RECORD_FILE)


def record_install(models_dir: Path, build: InstalledBuild) -> None:
    installs = read_installs(models_dir)
    installs[build.model_id] = build
    write_installs(models_dir, installs)


def forget_install(models_dir: Path, model_id: str) -> tuple[str, ...]:
    """Drop one build from the record and return the files that go with it."""
    installs = read_installs(models_dir)
    build = installs.pop(model_id, None)
    write_installs(models_dir, installs)
    if build is None:
        return (f"{model_id}.gguf", projector_filename(model_id))
    return build.files


def _plain(build: InstalledBuild) -> dict[str, Any]:
    plain = asdict(build)
    plain["weights"] = list(build.weights)
    plain["projector_gguf"] = dict(build.projector_gguf)
    return plain
