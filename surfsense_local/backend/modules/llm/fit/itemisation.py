"""What a load allocates, broken into the four things it is made of.

The estimator compares one number against a budget, but that number is a sum,
and a sum is untestable: it can be right for compensating wrong reasons. Naming
the parts is what lets a test assert that the weights term does not move when
the window does, and that the parts still add up to what the verdict reports.

It is also the shape the offload calculation needs, because only some of these
are things llama.cpp can move to the host.
"""

from dataclasses import dataclass

from modules.llm.fit.compute_buffers import compute_buffer_bytes
from modules.llm.fit.kv_cache import kv_cache_bytes
from modules.llm.fit.types import KvPrecision, ModelShape


@dataclass(frozen=True)
class NeedItems:
    """The four terms, each priced by its own module."""

    weights_bytes: int
    mmproj_bytes: int
    kv_bytes: int
    compute_bytes: int

    @property
    def total(self) -> int:
        """What the model allocates, which is what the verdict compares."""
        return (
            self.weights_bytes + self.mmproj_bytes + self.kv_bytes + self.compute_bytes
        )


def itemise(
    shape: ModelShape,
    weights_bytes: int,
    n_ctx: int,
    precision: KvPrecision = KvPrecision.F16,
    mmproj_bytes: int = 0,
) -> NeedItems:
    """Price one build at one window.

    The projector is a term of its own because `--fit` does not count it
    (llama.cpp issue #19980), so a vision model our sum calls resident can still
    fail to allocate. It is also not a thing the fitter can move, which is why
    the offload calculation needs it separated from the weights.
    """
    return NeedItems(
        weights_bytes=weights_bytes,
        mmproj_bytes=mmproj_bytes,
        kv_bytes=kv_cache_bytes(shape, n_ctx, precision),
        compute_bytes=compute_buffer_bytes(shape, n_ctx),
    )
