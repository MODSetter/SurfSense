"""Ollama's store: manifests that name content-addressed blobs.

`manifests/<host>/<namespace>/<model>/<tag>` is a small JSON document whose
`application/vnd.ollama.image.model` layer is the GGUF, in `blobs/` under its
digest with no extension, and whose `...image.projector` layer, when there is
one, is the vision projector Ollama pairs with it. Only manifests are parsed
here; the blobs are read by their headers later, like any other file.
"""

import json
from collections import defaultdict
from pathlib import Path

from modules.llm.catalog.local.engines.llamacpp.elsewhere.candidate import Candidate
from modules.llm.catalog.local.engines.llamacpp.elsewhere.places import App

_MODEL = "application/vnd.ollama.image.model"
_PROJECTOR = "application/vnd.ollama.image.projector"
# Ollama's own registry, whose library models it names without a host.
_REGISTRY = "registry.ollama.ai"
_LIBRARY = "library"
# A manifest is a few hundred bytes; anything far larger is not one.
_MOST_MANIFEST_BYTES = 1024 * 1024


def in_ollama(root: Path) -> list[Candidate]:
    """One candidate per model blob, named by the tag a person would type."""
    manifests = root / "manifests"
    by_blob: dict[Path, list[tuple[str, Path | None]]] = defaultdict(list)
    for manifest in _manifests(manifests):
        layers = _layers(manifest)
        model = _blob(root, layers.get(_MODEL))
        if model is None:
            continue
        by_blob[model].append(
            (
                _name(manifest.relative_to(manifests)),
                _blob(root, layers.get(_PROJECTOR)),
            )
        )
    return [
        Candidate(
            App.OLLAMA,
            blob,
            (blob,),
            projector=projector,
            name=name,
            source=name,
        )
        for blob, tags in by_blob.items()
        for name, projector in (_preferred(tags),)
    ]


def _manifests(manifests: Path) -> list[Path]:
    # host / namespace / model / tag, exactly four levels down.
    try:
        return sorted(p for p in manifests.glob("*/*/*/*") if p.is_file())
    except OSError:
        return []


def _layers(manifest: Path) -> dict[str, str]:
    try:
        if manifest.stat().st_size > _MOST_MANIFEST_BYTES:
            return {}
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    layers = document.get("layers") if isinstance(document, dict) else None
    found: dict[str, str] = {}
    for layer in layers if isinstance(layers, list) else []:
        if not isinstance(layer, dict):
            continue
        media, digest = layer.get("mediaType"), layer.get("digest")
        if isinstance(media, str) and isinstance(digest, str):
            found.setdefault(media, digest)
    return found


def _blob(root: Path, digest: str | None) -> Path | None:
    """`sha256:<hex>` is stored as `sha256-<hex>`; very old stores kept the colon."""
    if not digest or not digest.startswith("sha256:"):
        return None
    hex_digest = digest.removeprefix("sha256:")
    if not hex_digest.isalnum():
        return None
    for name in (f"sha256-{hex_digest}", f"sha256:{hex_digest}"):
        try:
            candidate = root / "blobs" / name
            if candidate.is_file():
                return candidate
        except (OSError, ValueError):
            continue
    return None


def _name(relative: Path) -> str:
    host, namespace, model, tag = relative.parts
    if host == _REGISTRY:
        prefix = "" if namespace == _LIBRARY else f"{namespace}/"
        return f"{prefix}{model}:{tag}"
    return f"{host}/{namespace}/{model}:{tag}"


def _preferred(tags: list[tuple[str, Path | None]]) -> tuple[str, Path | None]:
    """`qwen3:8b` over `qwen3:latest` for the same blob: it says which model."""
    return min(tags, key=lambda tag: (tag[0].endswith(":latest"), len(tag[0]), tag[0]))
