"""`transcription.json`, which Electron starts the speech recognition server
from and restarts it on every change. Written only when its bytes change, so an
API start, a voice install or a delete never cuts off a transcription.
"""

import json
from collections.abc import Sequence
from pathlib import Path

from modules.llm.catalog.local.engines.audiocpp.audio_folder.installed_recognisers import (
    InstalledRecogniser,
)

TRANSCRIPTION_CONFIG = "transcription.json"


def write_transcription_config(
    folder: Path, recognisers: Sequence[InstalledRecogniser], *, restart: bool = False
) -> None:
    """Replaced atomically. The server refuses an empty list, so with nothing
    installed the file goes, and Electron stops the server. `restart` rewrites
    it unchanged, which is what makes the server let go of its model's file."""
    path = folder / TRANSCRIPTION_CONFIG
    if not recognisers:
        path.unlink(missing_ok=True)
        return
    payload = {
        # Loaded on first use, so an idle app holds no speech model.
        "lazy_load": True,
        "models": [_entry(model) for model in recognisers],
    }
    written = (json.dumps(payload, indent=2) + "\n").encode()
    if not restart and path.is_file() and path.read_bytes() == written:
        return
    temporary = folder / f"{TRANSCRIPTION_CONFIG}.tmp"
    temporary.write_bytes(written)
    temporary.replace(path)


def _entry(model: InstalledRecogniser) -> dict:
    entry: dict = {
        "id": model.model_id,
        "family": model.family,
        "path": model.path.as_posix(),
        "task": "asr",
        # Phrases and windows are whole requests: no client streams audio up.
        "mode": "offline",
    }
    if options := model.transcription.request_options:
        # The multipart routes take no options, so the server merges these
        # under every request.
        entry["default_request_options"] = dict(options)
    return entry
