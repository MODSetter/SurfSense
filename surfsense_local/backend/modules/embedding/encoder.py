"""Text to vectors, run as the spec says, in process on the CPU."""

import hashlib
import logging
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from modules.embedding.bundled import bundled_dir, is_bundled
from modules.embedding.fp32_upcast import upcast
from modules.embedding.pooling import pool
from modules.embedding.precision import runs_at_fp32
from modules.embedding.spec import EmbedderSpec
from shared.config import get_storage_settings

log = logging.getLogger(__name__)

_PROVIDERS = ["CPUExecutionProvider"]


class Purpose(StrEnum):
    """Asymmetric models embed a question and a passage differently."""

    QUERY = "query"
    DOCUMENT = "document"


def model_dir(spec: EmbedderSpec) -> Path:
    """bge in the read-only pack the app ships; anything else where it downloaded."""
    if is_bundled(spec):
        return bundled_dir()
    return get_storage_settings().embedding_models_dir / spec.id


def missing_files(spec: EmbedderSpec) -> list[str]:
    """Files the model still needs before anything can be embedded."""
    directory = model_dir(spec)
    return [
        pinned.path
        for pinned in (spec.weights, spec.tokenizer)
        if not (directory / pinned.path).is_file()
    ]


def embed(spec: EmbedderSpec, texts: list[str], purpose: Purpose) -> list[list[float]]:
    """Embed every text with the spec's model, in batches."""
    prefix = spec.query_prefix if purpose is Purpose.QUERY else spec.document_prefix
    prefixed = [prefix + text for text in texts]
    vectors: list[list[float]] = []
    for start in range(0, len(prefixed), spec.batch):
        vectors.extend(_embed_batch(spec, prefixed[start : start + spec.batch]))

    wrong = next((len(v) for v in vectors if len(v) != spec.dimension), None)
    if wrong is not None:
        raise ValueError(
            f"{spec.id} returned {wrong} dimensions where its spec says "
            f"{spec.dimension}"
        )
    return vectors


def width(spec: EmbedderSpec, text: str) -> int:
    """How wide the model's vectors really are, whatever its spec says."""
    return len(_embed_batch(spec, [text])[0])


def _embed_batch(spec: EmbedderSpec, texts: list[str]) -> list[list[float]]:
    session, encoder = _loaded(spec, model_dir(spec))
    encoded = encoder.encode_batch(texts)
    feed = {
        "input_ids": np.array([e.ids for e in encoded], dtype=np.int64),
        "attention_mask": np.array([e.attention_mask for e in encoded], dtype=np.int64),
    }
    # Some exports drop token_type_ids; feed it only if the graph asks.
    inputs = {i.name for i in session.get_inputs()}
    if "token_type_ids" in inputs:
        feed["token_type_ids"] = np.array([e.type_ids for e in encoded], dtype=np.int64)
    # Decoder-style exports, Qwen3-Embedding's among them, take positions too.
    if "position_ids" in inputs:
        ids = feed["input_ids"]
        feed["position_ids"] = np.broadcast_to(
            np.arange(ids.shape[1]), ids.shape
        ).copy()

    output = session.run(None, feed)[0]
    pooled = pool(spec.pooling, output, feed["attention_mask"])
    if spec.normalize:
        pooled = pooled / np.linalg.norm(pooled, axis=1, keepdims=True)
    return pooled.astype(np.float32).tolist()


@lru_cache(maxsize=2)
def _loaded(spec: EmbedderSpec, directory: Path) -> tuple[Any, Any]:
    """One session and tokenizer per model, so a process follows the active index
    rather than whatever it loaded first."""
    import onnxruntime as ort
    from tokenizers import Tokenizer

    encoder = Tokenizer.from_file(str(directory / spec.tokenizer.path))
    encoder.enable_truncation(max_length=spec.max_tokens)
    encoder.enable_padding()
    session = _session(ort, spec, directory / spec.weights.path)
    return session, encoder


def _session(ort: Any, spec: EmbedderSpec, weights: Path) -> Any:
    """The pinned file upcast to FP32 where that runs faster, else the file as is."""
    # A missing file is left to the as-shipped open, which raises the real error.
    if runs_at_fp32(spec) and weights.is_file():
        try:
            session = ort.InferenceSession(
                upcast(_pinned_bytes(spec, weights)), providers=_PROVIDERS
            )
        except Exception:
            log.warning(
                "%s runs at FP16: its FP32 upcast failed", spec.id, exc_info=True
            )
        else:
            _drop_model_bytes(spec, session)
            return session
    return ort.InferenceSession(str(weights), providers=_PROVIDERS)


def _drop_model_bytes(spec: EmbedderSpec, session: Any) -> None:
    # The wrapper keeps the bytes to rebuild on a provider fallback, which a
    # CPU-only session never takes: 126 MB held per process for nothing.
    if hasattr(session, "_model_bytes"):
        session._model_bytes = None
    else:
        log.warning(
            "%s: onnxruntime has no _model_bytes to clear, so it may hold the "
            "upcast model for the session's life",
            spec.id,
        )


def _pinned_bytes(spec: EmbedderSpec, weights: Path) -> bytes:
    # The upcast was measured on this exact file; any other is opened as it is.
    model = weights.read_bytes()
    if hashlib.sha256(model).hexdigest() != spec.weights.sha256:
        raise ValueError(f"{weights} is not the {spec.id} file its spec pins")
    return model


def release_sessions() -> None:
    """Drop the cached sessions, and with them the model files they hold open.

    A delete calls this when Windows refuses to remove a model's file; the next
    embed loads its model again.
    """
    _loaded.cache_clear()
