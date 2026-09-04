"""Download the bundled embedding model for development and CI.

Run with `uv run scripts/fetch_embedding_model.py`. The packaged app ships it.
"""

import sys

import httpx

from worker.ingestion.embedding import EMBEDDING_FILES, EMBEDDING_REPO, embedding_dir

BASE = "https://huggingface.co"


def fetch(repo: str, files: list[str], into: object) -> None:
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
    fetch(EMBEDDING_REPO, EMBEDDING_FILES, embedding_dir())
    return 0


if __name__ == "__main__":
    sys.exit(main())
