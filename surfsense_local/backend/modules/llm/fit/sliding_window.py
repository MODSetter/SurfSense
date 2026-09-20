"""Which layers of a sliding-window model hold the full context.

The GGUF header states the window size but never the pattern, so the pattern is
a per-architecture fact. llama.cpp carries the same knowledge in `src/models`;
this is the subset that matters to the catalog, and anything absent is priced as
full attention rather than guessed at.
"""

# Global layers per cycle: a value of 6 means one layer in six attends to the
# whole context and the other five attend to `sliding_window` tokens.
_GLOBAL_LAYER_EVERY: dict[str, int] = {
    "gemma2": 2,
    "gemma3": 6,
    "gemma3n": 6,
    "cohere2": 4,
    "phi3": 2,
}


def global_layer_count(architecture: str, block_count: int) -> int | None:
    """How many layers attend to the whole window, or None when unknown.

    None is the honest answer for an architecture nobody has characterised, and
    the caller must then round up rather than assume a ratio.
    """
    cycle = _GLOBAL_LAYER_EVERY.get(architecture)
    if cycle is None:
        return None
    return block_count // cycle
