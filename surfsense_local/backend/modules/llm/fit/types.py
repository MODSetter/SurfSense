"""What the estimator reasons over: a model's shape and a machine's memory."""

from dataclasses import dataclass
from enum import StrEnum


class KvPrecision(StrEnum):
    """How the conversation cache is stored. Lossless either way; f16 costs twice
    the memory of q8_0 and needs no flash-attention kernel to be fast."""

    F16 = "f16"
    Q8_0 = "q8_0"

    @property
    def bytes_per_element(self) -> float:
        # q8_0 is one byte per weight plus a shared scale per 32-element block.
        return 2.0 if self is KvPrecision.F16 else 1.0 + 2.0 / 32.0


@dataclass(frozen=True)
class ModelShape:
    """Estimator inputs, named after the GGUF metadata keys they come from.

    Quantization-independent: measured, the architecture fields are identical
    across Q4_K_M, Q8_0 and f16 of the same model, so one header read prices
    every build of it.
    """

    architecture: str
    block_count: int
    head_count_kv: int
    key_length: int
    value_length: int
    context_length: int
    n_vocab: int
    sliding_window: int = 0
    expert_count: int = 0
