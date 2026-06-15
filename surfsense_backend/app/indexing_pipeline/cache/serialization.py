"""Serialize an EmbeddingSet to a compact, self-describing blob (no pickle).

Layout: ``MAGIC | uint32 header_len | json header | float32 matrix``. The header
carries the dim, chunk count, and ordered chunk texts; the matrix holds the
summary vector followed by one row per chunk, all float32 for compactness.
"""

from __future__ import annotations

import json
import struct

import numpy as np

from app.indexing_pipeline.cache.schemas import CachedChunk, EmbeddingSet

# Marker at the start of every blob: "SurfSense EMBeddings, version 1"-> SSEMB1. Lets us
# reject foreign blobs and bump the trailing digit if the layout ever changes.
_MAGIC = b"SSEMB1"
# 4-byte big-endian unsigned int written before the variable-length JSON header,
# so the reader knows where the header ends and the float matrix begins.
_HEADER_LEN = struct.Struct(">I")


def serialize(embedding_set: EmbeddingSet) -> bytes:
    summary = np.asarray(embedding_set.summary_embedding, dtype=np.float32).reshape(-1)
    dim = int(summary.shape[0])

    rows = [summary]
    texts: list[str] = []
    for chunk in embedding_set.chunks:
        vector = np.asarray(chunk.embedding, dtype=np.float32).reshape(-1)
        if vector.shape[0] != dim:
            raise ValueError("All vectors in an embedding set must share one dimension.")
        rows.append(vector)
        texts.append(chunk.text)

    matrix = np.stack(rows, axis=0)
    header = json.dumps(
        {"dim": dim, "count": len(texts), "texts": texts}, ensure_ascii=False
    ).encode("utf-8")
    return b"".join(
        [_MAGIC, _HEADER_LEN.pack(len(header)), header, matrix.tobytes(order="C")]
    )


def deserialize(blob: bytes) -> EmbeddingSet:
    view = memoryview(blob)
    if bytes(view[: len(_MAGIC)]) != _MAGIC:
        raise ValueError("Unrecognized embedding cache blob.")

    offset = len(_MAGIC)
    (header_len,) = _HEADER_LEN.unpack(view[offset : offset + _HEADER_LEN.size])
    offset += _HEADER_LEN.size

    header = json.loads(bytes(view[offset : offset + header_len]).decode("utf-8"))
    offset += header_len

    dim = int(header["dim"])
    count = int(header["count"])
    texts: list[str] = header["texts"]

    matrix = np.frombuffer(view[offset:], dtype=np.float32)
    if matrix.shape[0] != (count + 1) * dim:
        raise ValueError("Embedding cache blob is truncated or corrupt.")
    matrix = matrix.reshape(count + 1, dim)

    return EmbeddingSet(
        summary_embedding=matrix[0],
        chunks=[CachedChunk(text=texts[i], embedding=matrix[i + 1]) for i in range(count)],
    )
