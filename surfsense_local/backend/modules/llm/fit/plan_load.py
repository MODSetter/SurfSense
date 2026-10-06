"""The window, cache precision and slot count to load a model with.

Context is fixed at load, so this is decided once and cannot be renegotiated
mid-conversation. Three rules shape it:

- **Prefer residency over window.** KV is allocated upfront and competes with the
  weights, so maximising context silently demotes a model out of GPU residency.
  Widen only while the verdict stays FITS.
- **Prefer f16 over q8_0.** Quality is identical, but quantized cache requires a
  working flash-attention kernel, and when one is unavailable llama.cpp falls
  back to CPU attention silently. Take that dependency only where it pays.
- **Slots give way before residency does.** Four replies share one unified
  cache, which costs only a sliding layer's extra windows. Where four do not
  stay resident even at the floor, fewer do; where none would, four stay and
  `--fit` places the layers, since cutting slots cannot rescue that load.
"""

from dataclasses import dataclass

from modules.llm.fit.budget import HardwareBudget
from modules.llm.fit.estimate import (
    CONTEXT_FLOOR_TOKENS,
    CONTEXT_RUNGS,
    FitVerdict,
    estimate,
)
from modules.llm.fit.precision import FALLBACK, resident_precision
from modules.llm.fit.states import FitState
from modules.llm.fit.types import KvPrecision, ModelShape

# Replies the runtime serves at once, asked for on every backend. Fewer only
# when four would push a resident model out of the graphics card.
REQUESTED_SLOTS = 4


@dataclass(frozen=True)
class LoadPlan:
    n_ctx: int
    precision: KvPrecision
    verdict: FitVerdict
    slots: int = 1


def plan_load(
    shape: ModelShape,
    weights_bytes: int,
    budget: HardwareBudget,
    live: HardwareBudget | None = None,
    *,
    mmproj_bytes: int = 0,
    slots: int | None = None,
) -> LoadPlan:
    """Choose the slots, then the widest window that stays resident with them.

    Slots are priced at the floor: the question is whether a count can run
    resident at all, and the window search after it gives back whatever memory
    they leave. Unified memory keeps four, because its free-memory reading is
    the least reliable figure the plan has and `--fit` spills rather than fails.
    `slots` set skips the choice, for a caller that already knows the count.
    """
    if slots is None:
        slots = planned_slots(shape, weights_bytes, budget, mmproj_bytes=mmproj_bytes)
    return _plan_for(shape, weights_bytes, budget, live, mmproj_bytes, slots)


def planned_slots(
    shape: ModelShape,
    weights_bytes: int,
    budget: HardwareBudget,
    *,
    mmproj_bytes: int = 0,
) -> int:
    """How many replies a load serves at once: the most, up to four, that keep
    the model resident at the floor, or four where none would or on unified
    memory. One rule for the load and its badge, so the two cannot disagree."""
    if budget.uma:
        return REQUESTED_SLOTS
    floor = min(CONTEXT_FLOOR_TOKENS, shape.context_length or CONTEXT_FLOOR_TOKENS)
    for count in range(REQUESTED_SLOTS, 0, -1):
        resident = resident_precision(
            shape,
            weights_bytes,
            budget,
            n_ctx=floor,
            mmproj_bytes=mmproj_bytes,
            slots=count,
        )
        if resident is not None:
            return count
    return REQUESTED_SLOTS


def _plan_for(
    shape: ModelShape,
    weights_bytes: int,
    budget: HardwareBudget,
    live: HardwareBudget | None,
    mmproj_bytes: int,
    slots: int,
) -> LoadPlan:
    """Choose the widest window that stays resident, at the cheapest precision.

    The cap beats the floor. A model trained to 4096 tokens cannot be asked for
    8192 just because a grounded turn would like one: the floor describes what
    this app needs, not what a model can do.

    Two budgets, answering two questions. `budget` is capacity, and it decides
    the **verdict**, so the plan agrees with the badge the catalog already
    showed: a machine that is busy this second has not become one that cannot
    run the model. `live` is what is free right now, and it caps **widening**
    only, because context past the floor is opportunistic and on unified memory
    it is spent out of the same pool the OS is using.

    Without that split, a 1.7B took a 28,672 token window on an 8 GB Mac with
    2.3 GB reclaimable, the load paged, and it took 43 seconds.

    A cap in both directions. `live` can be the more generous of the two on an
    idle machine, and widening to fit a moment of free memory commits a window
    that only fits while nothing else is running, because the cache is allocated
    once at load and never shrinks. So widening stays inside whichever budget is
    tighter, which is also what keeps the verdict equal to the badge.
    """
    ceiling = shape.context_length or CONTEXT_FLOOR_TOKENS
    floor = min(CONTEXT_FLOOR_TOKENS, ceiling)

    # The same rule the badge is drawn from, so the screen and the load cannot
    # describe different configurations of the same model.
    precision = resident_precision(
        shape,
        weights_bytes,
        budget,
        n_ctx=floor,
        mmproj_bytes=mmproj_bytes,
        slots=slots,
    )

    if precision is None:
        # Nothing keeps it resident, so hold the floor and let --fit place the
        # layers. A cheaper cache buys nothing once layers are spilling anyway.
        return LoadPlan(
            n_ctx=floor,
            precision=FALLBACK,
            verdict=estimate(
                shape,
                weights_bytes,
                budget,
                n_ctx=floor,
                precision=FALLBACK,
                mmproj_bytes=mmproj_bytes,
                slots=slots,
            ),
            slots=slots,
        )

    # Widened against whichever budget is tighter, because `live` is a cap and a
    # cap must not raise a ceiling. On a busy machine that is `live`, which is
    # what stops a window being sized against memory the OS is already using. On
    # an idle one it is `budget`: widening to fit this moment's free memory
    # would commit a window that only fits while nothing else is running, and
    # the cache is allocated once at load and never shrinks.
    #
    # It also keeps the verdict below honest. Widening against a more generous
    # `live` and then reporting against `budget` produced a plan that said
    # PARTIAL for a row the catalog had badged FITS.
    widening = budget if live is None else min(budget, live, key=_headroom)
    n_ctx = _widest_resident(
        shape, weights_bytes, widening, precision, ceiling, floor, mmproj_bytes, slots
    )
    return LoadPlan(
        n_ctx=n_ctx,
        precision=precision,
        verdict=estimate(
            shape,
            weights_bytes,
            budget,
            n_ctx=n_ctx,
            precision=precision,
            mmproj_bytes=mmproj_bytes,
            slots=slots,
        ),
        slots=slots,
    )


def _headroom(budget: HardwareBudget) -> int:
    """What a widening search has to stay inside: the resident ceiling."""
    return budget.resident_bytes


def _widest_resident(
    shape: ModelShape,
    weights_bytes: int,
    budget: HardwareBudget,
    precision: KvPrecision,
    ceiling: int,
    floor: int,
    mmproj_bytes: int = 0,
    slots: int = 1,
) -> int:
    """Largest rung that stays resident, never a number between two rungs.

    A fixed, small set of candidates instead of a continuous search: the
    catalog badge, the preset and this plan can only ever quote one of
    `CONTEXT_RUNGS`, so the whole surface of windows a person can see is
    something a test can enumerate. `ceiling` (the model's own trained
    length, or a caller's cap) is tried too when it falls between two rungs,
    so a model is not held below what it was actually trained for; `floor`
    is always a candidate so the search never returns nothing.
    """
    candidates = {n for n in CONTEXT_RUNGS if floor <= n <= ceiling}
    candidates.add(floor)
    candidates.add(ceiling)
    for n_ctx in sorted(candidates, reverse=True):
        fits = (
            estimate(
                shape,
                weights_bytes,
                budget,
                n_ctx=n_ctx,
                precision=precision,
                mmproj_bytes=mmproj_bytes,
                slots=slots,
            ).state
            is FitState.FITS
        )
        if fits:
            return n_ctx
    return floor
