"""Does this model fit in this machine, and if not, how much spills.

    need   = weights + KV(window) + compute_buffers      what the model allocates
    usable = device_free - fit_reserve                   what --fit will use

The two subtractions sit on opposite sides of the comparison. Collapsing them
into one `overhead` term predicts residency for a configuration that measurably
spills, which is the specific failure this estimator exists to avoid.
"""

from dataclasses import dataclass

from modules.llm.fit.budget import HardwareBudget
from modules.llm.fit.compute_buffers import compute_buffer_bytes
from modules.llm.fit.kv_cache import kv_cache_bytes
from modules.llm.fit.states import FitState
from modules.llm.fit.types import KvPrecision, ModelShape

CONTEXT_FLOOR_TOKENS = 16384


@dataclass(frozen=True)
class FitVerdict:
    state: FitState
    need_bytes: int
    budget_bytes: int
    offload_fraction: float
    approximate: bool = False

    @property
    def can_install(self) -> bool:
        """Only physics refuses. Reduced speed runs, so it never blocks."""
        return self.state is not FitState.TOO_BIG


def estimate(
    shape: ModelShape,
    weights_bytes: int,
    budget: HardwareBudget,
    *,
    n_ctx: int = CONTEXT_FLOOR_TOKENS,
    precision: KvPrecision = KvPrecision.F16,
    mmproj_bytes: int = 0,
) -> FitVerdict:
    """Price one build against one device.

    `TOO_BIG` is evaluated at the context floor rather than the requested window:
    a model that will not fit at 16K cannot be rescued by a smaller context, and
    the remedy to offer is a smaller build.
    """
    # The projector is counted here because `--fit` does not count it:
    # llama.cpp issue #19980. Left out, a vision model our sum calls resident
    # can still fail to allocate on a tight machine.
    need = (
        weights_bytes
        + mmproj_bytes
        + kv_cache_bytes(shape, n_ctx, precision)
        + compute_buffer_bytes(n_ctx)
    )
    usable = budget.usable_vram_bytes

    floor_need = (
        weights_bytes
        + mmproj_bytes
        + kv_cache_bytes(shape, CONTEXT_FLOOR_TOKENS, precision)
        + compute_buffer_bytes(CONTEXT_FLOOR_TOKENS)
    )
    if floor_need > usable + budget.ram_available_bytes:
        return FitVerdict(
            state=FitState.TOO_BIG,
            need_bytes=need,
            budget_bytes=usable + budget.ram_available_bytes,
            offload_fraction=1.0,
        )

    if need <= usable:
        return FitVerdict(
            state=FitState.FITS,
            need_bytes=need,
            budget_bytes=usable,
            offload_fraction=0.0,
        )

    # > ponytail: this is the theoretical minimum spill, and llama.cpp spills in
    # > whole layers, so reality rounds up. Measured on an RTX 3050, Qwen3 4B
    # > spilled 602 MiB of weights plus 320 MiB of cache, f = 0.19, where this
    # > arithmetic gives 0.12. The states agree and the ordering agrees; the
    # > fraction does not. It matters because the badge copy is graded on it at
    # > 0.25 and 0.5, so calibrate against layer-granular placement before those
    # > thresholds are trusted.
    spilled = need - usable
    return FitVerdict(
        state=FitState.PARTIAL,
        need_bytes=need,
        budget_bytes=usable,
        offload_fraction=min(1.0, spilled / need),
    )
