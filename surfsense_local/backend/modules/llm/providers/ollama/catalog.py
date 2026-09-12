from typing import NamedTuple


class Offering(NamedTuple):
    """A model this provider knows how to pull, and its download size."""

    name: str
    label: str
    size_gb: float


# Ollama has no API that lists its library, so the models offered are curated.
# Qwen family for v1; sizes are the Q4_K_M builds Ollama serves by default.
OFFERINGS: tuple[Offering, ...] = (
    Offering("qwen3:0.6b", "Qwen3 0.6B", 0.5),
    Offering("qwen3:1.7b", "Qwen3 1.7B", 1.4),
    Offering("qwen3:4b", "Qwen3 4B", 2.6),
    Offering("qwen3:8b", "Qwen3 8B", 5.2),
    Offering("qwen3:14b", "Qwen3 14B", 9.3),
    Offering("qwen3:32b", "Qwen3 32B", 20.0),
    Offering("qwen2.5-coder:7b", "Qwen2.5 Coder 7B", 4.7),
    Offering("qwen2.5-coder:32b", "Qwen2.5 Coder 32B", 20.0),
)
