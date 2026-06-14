"""The cached payload: a document's chunk texts paired with their vectors."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class CachedChunk:
    text: str
    embedding: np.ndarray


@dataclass(frozen=True, slots=True)
class EmbeddingSet:
    """Everything the indexer needs to rebuild a document's chunks without embedding.

    ``summary_embedding`` is the document-level vector; ``chunks`` are the ordered
    chunk texts and their vectors.
    """

    summary_embedding: np.ndarray
    chunks: list[CachedChunk]

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)
