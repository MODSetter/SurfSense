"""Which layers of a sliding-window model hold the full context.

Three sources, in the order llama.cpp itself consults them. A header that states
its own pattern is the authority, as one flag per layer or as a period; only a
file that states neither falls back to the table below, which mirrors the
defaults each architecture passes to `load_swa_pattern`.

Anything absent from all three is priced as full attention on every layer. That
over-states memory, which is the only direction it is safe to be wrong in.
"""

from modules.llm.fit.types import ModelShape

# Period and whether the cycle leads with the full attention layer, matching the
# `n_pattern` and `dense_first` arguments in `src/models/*.cpp`. Read from
# llama.cpp at b11050; an architecture whose default nobody has verified is
# deliberately absent rather than guessed.
_DEFAULT_PATTERN: dict[str, tuple[int, bool]] = {
    "gemma2": (2, False),
    "gemma3": (6, False),
    "gemma3n": (5, False),
    "cohere2": (4, False),
    "gpt-oss": (2, False),
    "llama4": (4, False),
    "olmo2": (4, False),
    "exaone4": (4, False),
    "plamo3": (8, False),
    "afmoe": (4, False),
    "mellum": (4, False),
    "cohere2moe": (4, True),
    "modern-bert": (3, True),
    "smallthinker": (4, True),
}


def sliding_layers(shape: ModelShape) -> tuple[bool, ...] | None:
    """One flag per layer, True where the layer slides, or None when unknown.

    None is the honest answer for an architecture nobody has characterised, and
    the caller must then price every layer at full width rather than assume a
    ratio.
    """
    if shape.sliding_window_layers:
        return _fitted(shape.sliding_window_layers, shape.block_count)

    if shape.sliding_window_pattern > 0:
        return _from_period(shape.sliding_window_pattern, shape.block_count, False)

    default = _DEFAULT_PATTERN.get(shape.architecture)
    if default is None:
        return None
    period, dense_first = default
    return _from_period(period, shape.block_count, dense_first)


def _from_period(period: int, block_count: int, dense_first: bool) -> tuple[bool, ...]:
    """Expand a cycle length into one flag per layer.

    A period of six means one layer in six attends to the whole context. Which
    one depends on `dense_first`: normally the full attention layer closes the
    cycle, and for a handful of architectures it opens it.
    """
    if period <= 1:
        return (False,) * block_count
    if dense_first:
        return tuple(index % period != 0 for index in range(block_count))
    return tuple((index + 1) % period != 0 for index in range(block_count))


def _fitted(layers: tuple[bool, ...], block_count: int) -> tuple[bool, ...]:
    """The header's flags, cut or repeated to the model's depth.

    A header that disagrees with its own block count is a file we cannot read
    exactly, and repeating the cycle is what llama.cpp does with a short list.
    """
    if len(layers) == block_count:
        return layers
    return tuple(layers[index % len(layers)] for index in range(block_count))
