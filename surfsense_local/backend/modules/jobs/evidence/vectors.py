"""Passage vectors kept between runs, so a library that has not changed is not embedded again.

A run embeds every passage before its first question: about 25 seconds for 300 passages on a
laptop's CPU, and minutes for a large library. Vectors are kept in memory per embedder and
exact text, so the worker's next run over the same documents, and an eval's next run, start
answering at once. Queries differ per question and are not kept.
"""

from __future__ import annotations

import hashlib
import threading
from array import array
from collections import OrderedDict

from modules.jobs.evidence.retrieval import Embed

# About 3 KB a vector at 384 dimensions: 8,192 of them is some 26 MB, past most firms' libraries.
CAPACITY = 8_192

_kept: OrderedDict[tuple[str, bytes], array] = OrderedDict()
_lock = threading.Lock()


def remembered(embed: Embed, model: str) -> Embed:
    """`embed`, keeping each document vector by `model` (the embedder and its weights) and text."""

    def embedding(texts: list[str], query: bool) -> list[list[float]]:
        if query:
            return embed(texts, query)
        keys = [
            (model, hashlib.sha256(text.encode("utf-8")).digest()) for text in texts
        ]
        with _lock:
            found = {key: _kept[key] for key in keys if key in _kept}
            for key in found:
                _kept.move_to_end(key)
        missing = [index for index, key in enumerate(keys) if key not in found]
        fresh = embed([texts[index] for index in missing], False) if missing else []
        with _lock:
            for index, vector in zip(missing, fresh, strict=True):
                found[keys[index]] = _kept[keys[index]] = array("d", vector)
            while len(_kept) > CAPACITY:
                _kept.popitem(last=False)
        return [list(found[key]) for key in keys]

    return embedding


def forget() -> None:
    with _lock:
        _kept.clear()
