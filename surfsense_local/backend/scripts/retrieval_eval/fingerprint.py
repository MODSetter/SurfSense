"""What a built index was built from, so an unchanged run can reuse it.

Embedding a corpus is the slow part; ranking changes do not touch it. Keying
the database on the corpus and the embedder lets a ranking change be measured
in seconds and makes only an embedder or corpus change pay to index again.
"""

import hashlib
from pathlib import Path


def fingerprint(corpus_dir: Path, embedder: bytes) -> str:
    digest = hashlib.sha256()
    for path in sorted(corpus_dir.glob("*.md")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
        digest.update(b"\0")
    digest.update(embedder)
    return digest.hexdigest()[:16]


def embedder_identity(models_dir: Path, model_dir_name: str) -> bytes:
    """The embedding model as far as the index is concerned.

    Its files' names and sizes, not their contents: hashing 63 MB on every run
    to notice a swap nobody makes silently is not worth the second it costs.
    """
    directory = models_dir / model_dir_name
    parts = [model_dir_name]
    for path in sorted(directory.glob("*")) if directory.is_dir() else []:
        parts.append(f"{path.name}:{path.stat().st_size}")
    return "|".join(parts).encode("utf-8")
