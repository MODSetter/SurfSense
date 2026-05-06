"""Deterministic embedding fakes for E2E.

Mirrors the existing `patched_embed_texts` fixture in
`surfsense_backend/tests/integration/conftest.py`:

    MagicMock(side_effect=lambda texts: [[0.1] * _EMBEDDING_DIM for _ in texts])

The dimension matches whatever `config.embedding_model_instance.dimension`
returns in the running process so the fakes are vector-compatible with
the documents.embedding pgvector column.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.config import config

logger = logging.getLogger(__name__)


def _embedding_dim() -> int:
    """Resolve the dimension once, lazily, so tests work for any embedding model."""
    return int(config.embedding_model_instance.dimension)


def fake_embed_text(text: str) -> np.ndarray:
    """Deterministic single-text embedding."""
    return np.full(shape=(_embedding_dim(),), fill_value=0.1, dtype=np.float32)


def fake_embed_texts(texts: list[str]) -> list[np.ndarray]:
    """Deterministic batch embedding. One vector per input text."""
    if not texts:
        return []
    dim = _embedding_dim()
    return [
        np.full(shape=(dim,), fill_value=0.1, dtype=np.float32) for _ in texts
    ]


def install(patches: list[Any]) -> None:
    """Install embedding patches at every binding site we know about.

    Caller passes a `patches` list that the entrypoint will track in
    order to start them (and, in principle, stop them on shutdown — we
    intentionally never stop because the process exits when the test
    server stops).
    """
    from unittest.mock import patch as _patch

    targets = [
        # Source binding (where the real implementation lives)
        ("app.utils.document_converters.embed_text", fake_embed_text),
        ("app.utils.document_converters.embed_texts", fake_embed_texts),
        # Consumers that did `from app.utils.document_converters import embed_text/texts`
        ("app.indexing_pipeline.document_embedder.embed_text", fake_embed_text),
        ("app.indexing_pipeline.document_embedder.embed_texts", fake_embed_texts),
        # Pipeline service binding (the actual call site for indexing.index)
        ("app.indexing_pipeline.indexing_pipeline_service.embed_texts", fake_embed_texts),
    ]
    for target, replacement in targets:
        try:
            p = _patch(target, replacement)
            p.start()
            patches.append(p)
            logger.info("[fake-embeddings] patched %s", target)
        except (ModuleNotFoundError, AttributeError) as exc:
            # If a future refactor moves a binding, fail loudly — silent
            # passthrough to a real embedding model would be expensive
            # and non-deterministic.
            raise RuntimeError(
                f"Could not patch embedding binding {target!r}: {exc!s}. "
                f"Update surfsense_backend/tests/e2e/fakes/embeddings.py "
                f"to point at the new binding site."
            ) from exc
