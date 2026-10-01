"""Download the bundled embedding model for development, CI, and packaging.

`uv run scripts/fetch_embedding_model.py` places it where the app reads it in
development; pass a models root (`... models`) to stage it for an installer,
which electron-builder then copies into resources/models.

Fetched at bge's pinned revision and checked against its hashes: every existing
library was built with that exact file, so a different one is refused, not used.
"""

import hashlib
import sys
from pathlib import Path

import httpx

from modules.embedding.bundled import BGE, bundled_dir

BASE = "https://huggingface.co"


def fetch(into: Path) -> None:
    into.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        for pinned in (BGE.weights, BGE.tokenizer):
            target = into / pinned.path
            if not target.exists():
                print(f"get  {pinned.path}")
                url = f"{BASE}/{BGE.repo}/resolve/{BGE.revision}/{pinned.path}"
                with client.stream("GET", url) as reply:
                    reply.raise_for_status()
                    with target.open("wb") as sink:
                        for block in reply.iter_bytes():
                            sink.write(block)
            if _sha256(target) != pinned.sha256:
                target.unlink()
                raise SystemExit(f"{pinned.path} does not match bge's pinned hash")
            print(f"have {target}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    # Optional models root for staging an installer; defaults to the dev location.
    fetch(Path(sys.argv[1]) / BGE.id if len(sys.argv) > 1 else bundled_dir())
    return 0


if __name__ == "__main__":
    sys.exit(main())
