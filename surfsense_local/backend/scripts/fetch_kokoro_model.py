"""Download the Kokoro-82M voice model for offline podcast synthesis.

`uv run scripts/fetch_kokoro_model.py` places it where the app reads it in
development; pass a models root (`... models`) to stage it for an installer,
which electron-builder then copies into resources/models. The engine itself
(`kokoro-onnx`) is an optional dependency a podcast-shipping build adds.
"""

import sys
from pathlib import Path

import httpx

from worker.studio.tts import MODEL_DIR_NAME, MODEL_FILE, VOICES_FILE, kokoro_dir

# The maintained ONNX export and its packed voices.
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"


def fetch(into: Path) -> None:
    into.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=300.0) as client:
        for name in (MODEL_FILE, VOICES_FILE):
            target = into / name
            if target.exists():
                print(f"have {target}")
                continue
            print(f"get  {name}")
            with client.stream("GET", f"{BASE}/{name}") as reply:
                reply.raise_for_status()
                with target.open("wb") as sink:
                    for block in reply.iter_bytes():
                        sink.write(block)


def main() -> int:
    into = Path(sys.argv[1]) / MODEL_DIR_NAME if len(sys.argv) > 1 else kokoro_dir()
    fetch(into)
    return 0


if __name__ == "__main__":
    sys.exit(main())
