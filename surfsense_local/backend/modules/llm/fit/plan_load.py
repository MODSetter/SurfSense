"""The window and cache precision to load a model with.

Context is fixed at load, so this is decided once and cannot be renegotiated
mid-conversation. Two rules shape it:

- **Prefer residency over window.** KV is allocated upfront and competes with the
  weights, so maximising context silently demotes a model out of GPU residency.
  Widen only while the verdict stays FITS.
- **Prefer f16 over q8_0.** Quality is identical, but quantized cache requires a
  working flash-attention kernel, and when one is unavailable llama.cpp falls
  back to CPU attention silently. Take that dependency only where it pays.
"""

from dataclasses import dataclass

from modules.llm.fit.budget import HardwareBudget
from modules.llm.fit.estimate import CONTEXT_FLOOR_TOKENS, FitVerdict, estimate
from modules.llm.fit.states import FitState
from modules.llm.fit.types import KvPrecision, ModelShape


@dataclass(frozen=True)
class LoadPlan:
    n_ctx: int
    precision: KvPrecision
    verdict: FitVerdict


def plan_load(
    shape: ModelShape,
    weights_bytes: int,
    budget: HardwareBudget,
    live: HardwareBudget | None = None,
) -> LoadPlan:
    """Choose the widest window that stays resident, at the cheapest precision.

    The cap beats the floor. A model trained to 8192 tokens cannot be asked for
    16384 just because a grounded turn would like one: the floor describes what
    this app needs, not what a model can do.

    Two budgets, answering two questions. `budget` is capacity, and it decides
    the **verdict**, so the plan agrees with the badge the catalog already
    showed: a machine that is busy this second has not become one that cannot
    run the model. `live` is what is free right now, and it caps **widening**
    only, because context past the floor is opportunistic and on unified memory
    it is spent out of the same pool the OS is using.

    Without that split, a 1.7B took a 28,672 token window on an 8 GB Mac with
    2.3 GB reclaimable, the load paged, and it took 43 seconds.
    """
    ceiling = shape.context_length or CONTEXT_FLOOR_TOKENS
    floor = min(CONTEXT_FLOOR_TOKENS, ceiling)

    for precision in (KvPrecision.F16, KvPrecision.Q8_0):
        at_floor = estimate(
            shape, weights_bytes, budget, n_ctx=floor, precision=precision
        )
        if at_floor.state is not FitState.FITS:
            continue
        n_ctx = _widest_resident(
            shape, weights_bytes, live or budget, precision, ceiling, floor
        )
        return LoadPlan(
            n_ctx=n_ctx,
            precision=precision,
            verdict=estimate(
                shape, weights_bytes, budget, n_ctx=n_ctx, precision=precision
            ),
        )

    # Nothing keeps it resident, so hold the floor and let --fit place the layers.
    return LoadPlan(
        n_ctx=floor,
        precision=KvPrecision.F16,
        verdict=estimate(shape, weights_bytes, budget, n_ctx=floor),
    )


def _widest_resident(
    shape: ModelShape,
    weights_bytes: int,
    budget: HardwareBudget,
    precision: KvPrecision,
    ceiling: int,
    floor: int,
) -> int:
    """Binary search the window, in whole thousands of tokens."""
    low, high = floor, ceiling
    while low < high:
        mid = min(ceiling, (low + high + 1024) // 2)
        mid -= mid % 1024
        if mid <= low:
            break
        fits = (
            estimate(shape, weights_bytes, budget, n_ctx=mid, precision=precision).state
            is FitState.FITS
        )
        if fits:
            low = mid
        else:
            high = mid - 1024
    return max(floor, min(low, ceiling))
