"""`server.json`, which Electron starts audio.cpp's server from and restarts it
on every change. It names only the models: Electron's flags set the rest.
"""

import json
from collections.abc import Sequence
from pathlib import Path

from modules.llm.catalog.local.engines.audiocpp.audio_folder.installed import (
    InstalledAudio,
)

SERVER_CONFIG = "server.json"


def write_server_config(folder: Path, installed: Sequence[InstalledAudio]) -> None:
    """Replaced atomically. The server refuses an empty list, so with nothing
    installed the file goes, and Electron stops the server."""
    path = folder / SERVER_CONFIG
    if not installed:
        path.unlink(missing_ok=True)
        return
    payload = {
        # Loaded on first use, so an idle app holds no voice model.
        "lazy_load": True,
        "models": [
            {
                "id": model.model_id,
                "family": model.family,
                # Forward slashes: what audio.cpp was voiced with on Windows.
                "path": model.path.as_posix(),
                "task": "tts",
                "mode": "offline",
            }
            for model in installed
        ],
    }
    temporary = folder / f"{SERVER_CONFIG}.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)
