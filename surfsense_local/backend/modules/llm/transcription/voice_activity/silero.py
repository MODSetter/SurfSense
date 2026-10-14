"""Silero's probability of speech for each 32 ms frame, run on one thread:
the API's requests and the chat model need the rest."""

from functools import lru_cache
from pathlib import Path

import numpy as np

__all__ = ["FRAME_SECONDS", "frame_probabilities"]

_RATE = 16000
_FRAME = 512
# Silero v5 and later read each frame with the 64 samples before it.
_CONTEXT = 64
FRAME_SECONDS = _FRAME / _RATE


def frame_probabilities(pcm: bytes, model: Path) -> list[float]:
    """`pcm` is 16 kHz mono s16; the last frame is padded with silence."""
    session = _session(str(model))
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    state = np.zeros((2, 1, 128), dtype=np.float32)
    context = np.zeros((1, _CONTEXT), dtype=np.float32)
    rate = np.array(_RATE, dtype=np.int64)
    probabilities = []
    for start in range(0, len(samples), _FRAME):
        frame = samples[start : start + _FRAME]
        frame = np.pad(frame, (0, _FRAME - len(frame)))[None, :]
        both = np.concatenate([context, frame], axis=1)
        out, state = session.run(None, {"input": both, "state": state, "sr": rate})
        context = both[:, -_CONTEXT:]
        probabilities.append(float(out[0, 0]))
    return probabilities


@lru_cache(maxsize=1)
def _session(model: str):
    # Lazily: the API starts without paying for onnxruntime's import.
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return ort.InferenceSession(model, options, providers=["CPUExecutionProvider"])
