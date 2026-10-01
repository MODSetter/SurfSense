"""What a built index was built from, so an unchanged run can reuse it.

Embedding a corpus is the slow part; ranking changes do not touch it. Keying
the database on the corpus and the embedder lets a ranking change be measured
in seconds and makes only an embedder or corpus change pay to index again.
"""

import hashlib
import json
from pathlib import Path


def fingerprint(*corpus_dirs: Path, embedder: bytes, tokenizer: str) -> str:
    """Every document that will be indexed, and the two rules that turn it into one.

    The tokenizer belongs here with the embedder: it decides the terms the
    keyword leg scores, so changing it changes the index as surely as a new
    model does.
    """
    digest = hashlib.sha256()
    for corpus_dir in corpus_dirs:
        for path in sorted(corpus_dir.glob("*.md")) if corpus_dir.is_dir() else []:
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
            digest.update(b"\0")
    digest.update(embedder)
    digest.update(tokenizer.encode("utf-8"))
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


def curated_identity(model_id: str) -> bytes:
    """A curated embedder by what pins it: its id and its weights' hash, read
    from the manifest file without importing the app."""
    manifest = Path(__file__).resolve().parents[2] / (
        "modules/llm/catalog/local/manifest/models.json"
    )
    for model in json.loads(manifest.read_text())["models"]:
        if model["id"] == model_id:
            weights = model["builds"][0]["files"][0]
            return f"{model_id}|{weights['sha256']}".encode()
    raise ValueError(f"no curated embedder named {model_id}")
