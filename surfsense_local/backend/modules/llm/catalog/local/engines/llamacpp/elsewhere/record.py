"""What SurfSense remembers about models other apps keep: which it uses in
place, whether to look in those apps' folders, and which folders a person added.

Kept beside the preset in the models folder, so it moves with it, and kept
apart from `installs.json`: everything that record names is SurfSense's to
delete, and nothing this one names ever is.
"""

import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from modules.llm.catalog.local.engines.llamacpp.elsewhere.places import App
from modules.llm.catalog.local.quantization import UNKNOWN

if TYPE_CHECKING:
    # Typing only: the scan reads the folder's own models, which import this.
    from modules.llm.catalog.local.engines.llamacpp.elsewhere.find import FoundModel

RECORD_FILE = "elsewhere.json"

# The start of each in-place model's name, so it reads as whose file it is and
# never meets a file SurfSense downloaded.
_PREFIX = {
    App.OLLAMA: "ollama",
    App.LM_STUDIO: "lmstudio",
    App.HUGGING_FACE: "hf",
    App.LLAMA_CPP: "llamacpp",
    App.JAN: "jan",
    App.GPT4ALL: "gpt4all",
    App.FOLDER: "local",
}
# What a preset section, a URL path segment and a file name can all carry.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_LONGEST = 80


@dataclass(frozen=True)
class InPlace:
    """A model SurfSense uses where another app keeps it."""

    # The runtime's name for it: the preset section, the selection's name.
    model_id: str
    app: App
    path: str
    parts: tuple[str, ...]
    projector: str | None
    # What it was called when chosen, for the screens.
    name: str
    source: str | None = None


@dataclass(frozen=True)
class ElsewhereRecord:
    # Whether to look in other apps' folders. Added folders are read either way.
    look: bool = True
    folders: tuple[str, ...] = ()
    models: tuple[InPlace, ...] = ()


def read_record(models_dir: Path) -> ElsewhereRecord:
    try:
        raw = json.loads((models_dir / RECORD_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ElsewhereRecord()
    if not isinstance(raw, dict):
        return ElsewhereRecord()
    models = []
    for item in raw.get("models", []):
        try:
            models.append(
                InPlace(
                    model_id=str(item["model_id"]),
                    app=App(item["app"]),
                    path=str(item["path"]),
                    parts=tuple(str(p) for p in item.get("parts") or [item["path"]]),
                    projector=item.get("projector"),
                    name=str(item.get("name") or item["model_id"]),
                    source=item.get("source"),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    folders = raw.get("folders", [])
    return ElsewhereRecord(
        look=raw.get("look", True) is not False,
        folders=tuple(str(f) for f in folders if isinstance(f, str)),
        models=tuple(models),
    )


def write_record(models_dir: Path, record: ElsewhereRecord) -> None:
    """Replaced atomically, so a half-written record never names a model."""
    models_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "look": record.look,
        "folders": list(record.folders),
        "models": [_plain(model) for model in record.models],
    }
    temporary = models_dir / f"{RECORD_FILE}.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(models_dir / RECORD_FILE)


def use_in_place(models_dir: Path, found: "FoundModel") -> InPlace:
    """Record a found model for use where it lies. The same file keeps the
    name it was given, so a selection naming it stays good."""
    record = read_record(models_dir)
    path = str(found.path)
    for model in record.models:
        if model.path == path:
            return model
    used = InPlace(
        model_id=_new_id(models_dir, record, found),
        app=found.app,
        path=path,
        parts=tuple(str(part) for part in found.parts),
        projector=str(found.projector) if found.projector else None,
        name=found.label.name,
        source=found.source,
    )
    write_record(models_dir, replace(record, models=(*record.models, used)))
    return used


def forget(models_dir: Path, model_id: str) -> bool:
    """Stop using a model in place. Its file is not touched. False when the
    record never named it."""
    record = read_record(models_dir)
    kept = tuple(m for m in record.models if m.model_id != model_id)
    if len(kept) == len(record.models):
        return False
    write_record(models_dir, replace(record, models=kept))
    return True


def in_place(models_dir: Path, model_id: str) -> InPlace | None:
    return next(
        (m for m in read_record(models_dir).models if m.model_id == model_id), None
    )


def in_place_path(models_dir: Path, model_id: str) -> Path | None:
    used = in_place(models_dir, model_id)
    return Path(used.path) if used else None


def set_look(models_dir: Path, look: bool) -> ElsewhereRecord:
    record = replace(read_record(models_dir), look=look)
    write_record(models_dir, record)
    return record


def add_folder(models_dir: Path, folder: Path) -> ElsewhereRecord:
    record = read_record(models_dir)
    if str(folder) not in record.folders:
        record = replace(record, folders=(*record.folders, str(folder)))
        write_record(models_dir, record)
    return record


def remove_folder(models_dir: Path, folder: Path) -> ElsewhereRecord:
    record = read_record(models_dir)
    record = replace(
        record, folders=tuple(f for f in record.folders if f != str(folder))
    )
    write_record(models_dir, record)
    return record


def _new_id(models_dir: Path, record: ElsewhereRecord, found: "FoundModel") -> str:
    label = found.label
    words = [_PREFIX[found.app], label.name]
    # An Ollama tag is unique to its blob; elsewhere one model's builds share a name.
    if (
        found.app is not App.OLLAMA
        and label.quantization != UNKNOWN
        and label.quantization.lower() not in label.name.lower()
    ):
        words.append(label.quantization)
    base = _UNSAFE.sub("-", "-".join(words)).strip("-._")[:_LONGEST] or "model"
    taken = {m.model_id.lower() for m in record.models} | _folder_names(models_dir)
    name, n = base, 1
    while name.lower() in taken:
        n += 1
        name = f"{base}-{n}"
    return name


def _folder_names(models_dir: Path) -> set[str]:
    """What the router calls the folder's own files: each file's stem."""
    try:
        return {p.stem.lower() for p in models_dir.glob("*.gguf")}
    except OSError:
        return set()


def _plain(model: InPlace) -> dict[str, Any]:
    plain = asdict(model)
    plain["app"] = model.app.value
    plain["parts"] = list(model.parts)
    return plain
