"""Whether a model SurfSense did not measure works, after its download."""

from dataclasses import dataclass

from modules.embedding.encoder import Purpose, embed, width
from modules.embedding.search_check import search_check
from modules.embedding.spec import EmbedderSpec

PROBE = "The scanner battery lasts about ten hours on a full charge."


@dataclass(frozen=True)
class Refusal:
    """Why a model failed its check: the sentence a person reads, and its two
    counts raw, for an interface that words the refusal itself."""

    message: str
    found: int
    asked: int


def verify(spec: EmbedderSpec) -> tuple[int, Refusal | None]:
    """Its real width, and why it is refused, or None. The probe's width wins
    over the config's, which a model with a projection layer gets wrong."""
    probed = spec.model_copy(update={"dimension": width(spec, PROBE)})
    result = search_check(
        lambda texts: _embed(probed, texts, Purpose.QUERY),
        lambda texts: _embed(probed, texts, Purpose.DOCUMENT),
    )
    if not result.passed:
        return probed.dimension, Refusal(
            f"It found {result.first} of {result.asked} answers first; a search "
            f"model has to find all {result.asked}.",
            found=result.first,
            asked=result.asked,
        )
    return probed.dimension, None


def _embed(spec: EmbedderSpec, texts: list[str], purpose: Purpose) -> list[list[float]]:
    return embed(spec, texts, purpose)
