"""Identity of a cacheable embedding set: equal keys yield identical vectors.

Embeddings depend on the markdown text, the embedding model, and the chunker --
never on how the markdown was produced. So the key is the markdown's own hash
plus the model and chunker recipe, not the upstream parse identity.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmbeddingKey:
    markdown_sha256: str
    embedding_model: str
    embedding_dim: int
    chunker_kind: str
    chunker_version: int

    @property
    def object_suffix(self) -> str:
        # Fingerprint the model so distinct models never share a blob, while the
        # markdown hash (the object's folder) stays human-readable.
        fingerprint = hashlib.sha256(self.embedding_model.encode("utf-8")).hexdigest()
        return f"{fingerprint[:16]}.{self.chunker_kind}.v{self.chunker_version}.emb"
