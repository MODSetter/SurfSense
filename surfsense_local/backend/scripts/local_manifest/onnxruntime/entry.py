"""The hand-authored part of an embedding model's entry.

Beyond what every entry names, a person reviews what no file states: the width,
pooling and prefixes the index's spec needs, the ranking weight the retrieval
eval measured, and how close a converted build's vectors are to the original.
"""

from dataclasses import dataclass, field
from typing import Any

from local_manifest.entry import Entry


@dataclass(frozen=True)
class EmbeddingEntry(Entry):
    # (label, weights path) to pin, most preferred first: the first is the default.
    builds: tuple[tuple[str, str], ...] = ()
    tokenizer: str = "tokenizer.json"
    # `EmbeddingDefaults` as the manifest writes it.
    embedding: dict[str, Any] = field(default_factory=dict)
