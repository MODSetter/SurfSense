"""Which cache precision a build will actually be loaded with.

One rule, in one place, because four callers need the same answer and disagreeing
about it is a screen that describes a load the app will not perform. The badge
said `Reduced speed` for a model the loader then placed entirely on the GPU,
purely because the badge priced f16 and the loader chose q8_0.

The rule: prefer f16, and take q8_0 only where it converts a spill into
residency. Quality is identical either way, but a quantized cache needs a
working fused flash attention kernel, and where one is missing llama.cpp falls
back to CPU attention silently. That is a dependency worth taking to keep a
model on the device, and not worth taking for nothing.

Evaluated at the context floor, because that is the window the app guarantees
and the one the verdict is about. Widening past it is opportunistic and belongs
to `plan_load`.

> ponytail: whether q8_0 is the right trade at all is the open measurement in
> `07-llamacpp-runtime.md`. Unsloth measured a quantized cache at 35 % slower
> generation, which if it reproduces here means preferring a small spill instead.
> Until then the badge's job is to agree with the loader, whatever the loader
> does, which is exactly what this shared rule buys.
"""

from modules.llm.fit.budget import HardwareBudget
from modules.llm.fit.estimate import CONTEXT_FLOOR_TOKENS, estimate
from modules.llm.fit.states import FitState
from modules.llm.fit.types import KvPrecision, ModelShape

# In preference order. The first that keeps the model resident wins.
_LADDER = (KvPrecision.F16, KvPrecision.Q8_0)

# What a load falls back to when no precision keeps the model resident. The
# cheaper cache buys nothing once layers are spilling anyway, so it would take
# the flash attention dependency for no gain.
FALLBACK = KvPrecision.F16


def resident_precision(
    shape: ModelShape,
    weights_bytes: int,
    budget: HardwareBudget,
    *,
    n_ctx: int = CONTEXT_FLOOR_TOKENS,
    mmproj_bytes: int = 0,
) -> KvPrecision | None:
    """The cheapest cache that keeps this build resident, or None if none does.

    None is meaningful: it says no cache choice rescues this model, so the
    caller reports whatever f16 gives rather than pretending a quantized cache
    changed the answer.
    """
    for precision in _LADDER:
        verdict = estimate(
            shape,
            weights_bytes,
            budget,
            n_ctx=n_ctx,
            precision=precision,
            mmproj_bytes=mmproj_bytes,
        )
        if verdict.state is FitState.FITS:
            return precision
    return None


def planned_precision(
    shape: ModelShape,
    weights_bytes: int,
    budget: HardwareBudget,
    *,
    n_ctx: int = CONTEXT_FLOOR_TOKENS,
    mmproj_bytes: int = 0,
) -> KvPrecision:
    """The precision a load will use, resident or not.

    What a badge wants: it has to name one, and it has to name the one the
    loader would pick.
    """
    return (
        resident_precision(
            shape, weights_bytes, budget, n_ctx=n_ctx, mmproj_bytes=mmproj_bytes
        )
        or FALLBACK
    )
