"""How much of a build is read to decode one token.

Authoring time only. A dense model reads every weight per token and the answer
is 1.0; a mixture of experts reads its shared weights plus the few experts the
router picked, which is the whole reason such a model is worth shipping to a
machine that could not hold a dense one of the same size.

Both halves come from llama.cpp rather than from conventions restated here: the
sizes from its quantization table, and the expert tensor names from its own
tensor name table. A rename upstream is then an import error rather than a
pattern that quietly stops matching and reports every mixture of experts as
dense.
"""

from gguf.constants import (
    GGML_QUANT_SIZES,
    MODEL_TENSOR,
    TENSOR_NAMES,
    GGMLQuantizationType,
)

from modules.llm.gguf import GgufHeader, HeaderTensor

# The expert weights a router reads per token, as llama.cpp defines that set.
# Its own fitter matches `blk.\d+.ffn_(up|down|gate_up|gate)_(ch|)exps` and calls
# that comment "matches all MoE tensors" (common/fit.cpp), which is the same
# seven members below and deliberately not `ffn_norm_exps`: a per expert norm is
# a vector beside these matrices, and the set that decides what llama.cpp moves
# to the host is the set that decides what it reads from the host.
_EXPERT_TENSORS = (
    MODEL_TENSOR.FFN_UP_EXP,
    MODEL_TENSOR.FFN_DOWN_EXP,
    MODEL_TENSOR.FFN_GATE_EXP,
    MODEL_TENSOR.FFN_GATE_UP_EXP,
    MODEL_TENSOR.FFN_UP_CHEXP,
    MODEL_TENSOR.FFN_DOWN_CHEXP,
    MODEL_TENSOR.FFN_GATE_CHEXP,
)

# "blk.{bid}.ffn_up_exps" -> "ffn_up_exps". The part that names what a tensor is,
# with the block number and any "weight" suffix left to the comparison.
_EXPERT_KINDS = frozenset(
    TENSOR_NAMES[tensor].rsplit(".", 1)[-1] for tensor in _EXPERT_TENSORS
)


def is_expert(name: str) -> bool:
    """Whether a tensor is one the router reads only for the experts it picked.

    Compared segment by segment rather than by substring: `blk.0.ffn_up_exps`
    and `blk.0.ffn_up_exps.weight` are the same tensor, and a name that merely
    contains one of these words is not.
    """
    return any(part in _EXPERT_KINDS for part in name.split("."))


def tensor_bytes(tensor: HeaderTensor) -> int:
    """Bytes one tensor occupies, or 0 for a type this build cannot size.

    Zero rather than an exception: an unknown id is one tensor we cannot price,
    not a header we should refuse, and the caller is computing a ratio.
    """
    try:
        block_size, type_size = GGML_QUANT_SIZES[GGMLQuantizationType(tensor.ggml_type)]
    except (ValueError, KeyError):
        return 0
    elements = 1
    for dim in tensor.dims:
        elements *= dim
    return elements * type_size // block_size


def decode_fraction(header: GgufHeader, expert_used_count: int, expert_count: int) -> float:
    """Fraction of the file's bytes read per decoded token.

    Dense models return exactly 1.0, including any model whose header does not
    describe experts at all, so the field is safe to write for every entry.
    """
    if expert_count <= 0 or expert_used_count <= 0 or expert_used_count >= expert_count:
        return 1.0

    total = 0
    read = 0.0
    active = expert_used_count / expert_count
    for tensor in header.tensors:
        size = tensor_bytes(tensor)
        total += size
        read += size * active if is_expert(tensor.name) else size
    if total <= 0:
        return 1.0
    return round(read / total, 4)
