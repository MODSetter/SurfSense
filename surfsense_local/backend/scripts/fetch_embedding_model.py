"""Download the bundled embedding model for development, CI, and packaging.

`uv run scripts/fetch_embedding_model.py` places it where the app reads it in
development; pass a models root (`... models`) to stage it for an installer,
which electron-builder then copies into resources/models.
"""

import sys
from pathlib import Path

import httpx

from worker.ingestion.embedding import (
    EMBEDDING_FILES,
    EMBEDDING_REPO,
    MODEL_DIR_NAME,
    embedding_dir,
)

BASE = "https://huggingface.co"


def fetch(repo: str, files: list[str], into: Path) -> None:
    into.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        for name in files:
            target = into / name
            if target.exists():
                print(f"have {target}")
                continue
            print(f"get  {name}")
            with client.stream("GET", f"{BASE}/{repo}/resolve/main/{name}") as reply:
                reply.raise_for_status()
                with target.open("wb") as sink:
                    for block in reply.iter_bytes():
                        sink.write(block)


def main() -> int:
    # Optional models root for staging an installer; defaults to the dev location.
    into = Path(sys.argv[1]) / MODEL_DIR_NAME if len(sys.argv) > 1 else embedding_dir()
    fetch(EMBEDDING_REPO, EMBEDDING_FILES, into)
    return 0


if __name__ == "__main__":
    sys.exit(main())
