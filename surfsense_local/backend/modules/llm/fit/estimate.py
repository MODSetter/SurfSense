"""Does this model fit in this machine, and if not, how much spills.

    need     = weights + KV(window) + compute_buffers    what the model allocates
    resident = what it must fit inside to run at full speed
    refusal  = what physics allows at all

The two subtractions sit on opposite sides of the comparison. Collapsing them
into one `overhead` term predicts residency for a configuration that measurably
spills, which is the specific failure this estimator exists to avoid.

`resident` and `refusal` come from the budget rather than being assembled here,
because what they mean depends on the machine: they are two pools on a discrete
card, one pool on unified memory, and the same number on a machine with no GPU
at all. Assembling them here is what badged every model on a CPU only laptop as
spilling from a graphics card it does not have.
"""

from dataclasses import dataclass

from modules.llm.fit.budget import HardwareBudget
from modules.llm.fit.itemisation import itemise
from modules.llm.fit.offload import offload_fraction
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
    items = itemise(shape, weights_bytes, n_ctx, precision, mmproj_bytes)
    need = items.total
    # Two questions, two numbers, and the budget owns the difference between
    # them. On a discrete card residency is the card and physics is the card plus
    # the host; on unified memory both are the one pool; without a GPU both are
    # the processor's own memory, which is what makes the middle state
    # unreachable there rather than something the states have to special case.
    resident = budget.resident_bytes
    refusal = budget.refusal_bytes

    floor = itemise(shape, weights_bytes, CONTEXT_FLOOR_TOKENS, precision, mmproj_bytes)
    if floor.total > refusal:
        return FitVerdict(
            state=FitState.TOO_BIG,
            need_bytes=need,
            budget_bytes=refusal,
            offload_fraction=1.0,
        )

    if need <= resident:
        return FitVerdict(
            state=FitState.FITS,
            need_bytes=need,
            budget_bytes=resident,
            offload_fraction=0.0,
        )

    if need > refusal:
        # Past the floor check, which asked whether a smaller window would
        # rescue this model. It would not rescue this *window*, and there is no
        # third place to put the excess, so the requested window is refused
        # rather than described as a partial offload.
        #
        # Reachable only where residency and physics are the same number, which
        # means a machine with no GPU: the model is already entirely on the
        # processor, so calling it partly offloaded names a device that is not
        # there. Found by the property sweep, not by a fixture.
        return FitVerdict(
            state=FitState.TOO_BIG,
            need_bytes=need,
            budget_bytes=refusal,
            offload_fraction=1.0,
        )

    return FitVerdict(
        state=FitState.PARTIAL,
        need_bytes=need,
        budget_bytes=resident,
        offload_fraction=offload_fraction(shape, items, resident),
    )
