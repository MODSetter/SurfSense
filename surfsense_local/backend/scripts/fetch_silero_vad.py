"""Stage Silero VAD, which keeps silence away from the speech model, into the
models pack beside the bundled voice.

`uv run scripts/fetch_silero_vad.py` places it where the app reads it in
development; pass a models root (`... models`) to stage it for an installer,
which electron-builder copies into resources/models. Both files come from the
pinned commit and are sha256-checked; the API and the worker read them in place.
"""

import hashlib
import sys
from pathlib import Path

import httpx

from modules.llm.transcription.voice_activity.model_file import (
    SILERO_VAD,
    VAD_DIR_NAME,
    PinnedVad,
    silero_vad_dir,
)

BASE = "https://raw.githubusercontent.com"


def stage(
    into: Path,
    pin: PinnedVad = SILERO_VAD,
    *,
    transport: httpx.BaseTransport | None = None,
) -> None:
    into.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        follow_redirects=True, timeout=120.0, transport=transport
    ) as client:
        for pinned in (pin.weights, pin.licence):
            target = into / pinned.name
            if target.exists() and _sha256(target) == pinned.sha256:
                print(f"have {target}")
                continue
            print(f"get  {pinned.path}")
            reply = client.get(f"{BASE}/{pin.repo}/{pin.commit}/{pinned.path}")
            reply.raise_for_status()
            if hashlib.sha256(reply.content).hexdigest() != pinned.sha256:
                raise SystemExit(f"{pinned.path} does not match the pinned hash")
            partial = target.with_name(f"{target.name}.part")
            partial.write_bytes(reply.content)
            partial.replace(target)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    # Optional models root for staging an installer; defaults to the dev location.
    stage(Path(sys.argv[1]) / VAD_DIR_NAME if len(sys.argv) > 1 else silero_vad_dir())
    return 0


if __name__ == "__main__":
    sys.exit(main())
