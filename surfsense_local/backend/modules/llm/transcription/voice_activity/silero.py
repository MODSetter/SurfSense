"""Silero's probability of speech for each 32 ms frame, run on one thread:
the API's requests and the chat model need the rest."""

from functools import lru_cache
from pathlib import Path

import numpy as np

__all__ = ["FRAME_BYTES", "FRAME_SECONDS", "SileroReader", "frame_probabilities"]

_RATE = 16000
_FRAME = 512
# Silero v5 and later read each frame with the 64 samples before it.
_CONTEXT = 64
FRAME_SECONDS = _FRAME / _RATE
FRAME_BYTES = _FRAME * 2


class SileroReader:
    """One stream of 16 kHz mono s16 PCM read piece by piece, as a recording
    is read off disk: each piece continues where the last ended."""

    def __init__(self, model: Path) -> None:
        self._session = _session(str(model))
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, _CONTEXT), dtype=np.float32)
        self._rate = np.array(_RATE, dtype=np.int64)

    def read(self, pcm: bytes) -> list[float]:
        """Every piece but the last holds whole frames (FRAME_BYTES each); the
        last frame is padded with silence."""
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
        probabilities = []
        for start in range(0, len(samples), _FRAME):
            frame = samples[start : start + _FRAME]
            frame = np.pad(frame, (0, _FRAME - len(frame)))[None, :]
            both = np.concatenate([self._context, frame], axis=1)
            out, self._state = self._session.run(
                None, {"input": both, "state": self._state, "sr": self._rate}
            )
            self._context = both[:, -_CONTEXT:]
            probabilities.append(float(out[0, 0]))
        return probabilities


def frame_probabilities(pcm: bytes, model: Path) -> list[float]:
    """`pcm` is 16 kHz mono s16; the last frame is padded with silence."""
    return SileroReader(model).read(pcm)


@lru_cache(maxsize=1)
def _session(model: str):
    # Lazily: the API starts without paying for onnxruntime's import.
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return ort.InferenceSession(model, options, providers=["CPUExecutionProvider"])
