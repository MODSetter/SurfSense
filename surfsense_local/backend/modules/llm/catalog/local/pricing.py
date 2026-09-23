"""One price for a build, whatever its origin: exact from a shape, else estimated
from the listing's sizes.

Exact pricing is the loader's own rule, at the cache precision it would choose,
with the projector counted, so a badge describes the load the app performs. An
estimate exists so opening a searched repo costs one listing and no header read.
It over-charges on purpose: a size-only shape charges no KV cache at all, which
on an 8 GB card would call a spill resident. The exact figure replaces it before
any bytes move.
"""

import dataclasses

from modules.llm.fit import (
    FitVerdict,
    HardwareBudget,
    ModelShape,
    estimate,
    planned_precision,
)

# Unsloth Studio's size-only rule: activations run about 15% over the weights,
# and a flat gibibyte covers a working context.
_ACTIVATIONS = 0.15
_CONTEXT_ALLOWANCE = 1024**3

_SIZE_ONLY = ModelShape(
    architecture="",
    block_count=0,
    head_count_kv=0,
    key_length=0,
    value_length=0,
    context_length=0,
    n_vocab=0,
)


def exact_price(
    shape: ModelShape, weights_bytes: int, projector_bytes: int, budget: HardwareBudget
) -> FitVerdict:
    precision = planned_precision(
        shape, weights_bytes, budget, mmproj_bytes=projector_bytes
    )
    return estimate(
        shape, weights_bytes, budget, precision=precision, mmproj_bytes=projector_bytes
    )


def estimated_price(
    weights_bytes: int, projector_bytes: int, budget: HardwareBudget
) -> FitVerdict:
    charged = int(weights_bytes * (1 + _ACTIVATIONS)) + _CONTEXT_ALLOWANCE
    verdict = estimate(_SIZE_ONLY, charged, budget, mmproj_bytes=projector_bytes)
    return dataclasses.replace(verdict, approximate=True)


def price(
    shape: ModelShape | None,
    weights_bytes: int,
    projector_bytes: int,
    budget: HardwareBudget,
) -> FitVerdict:
    if shape is None or not shape.block_count:
        return estimated_price(weights_bytes, projector_bytes, budget)
    return exact_price(shape, weights_bytes, projector_bytes, budget)
