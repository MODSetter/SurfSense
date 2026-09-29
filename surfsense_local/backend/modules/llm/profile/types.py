from dataclasses import dataclass
from enum import StrEnum


class Tier(StrEnum):
    """How much prompt structure a model wants. The value names its prompt file."""

    COMPACT = "compact"
    CAPABLE = "capable"
    FRONTIER = "frontier"


class Line(StrEnum):
    """Where a model sits in its own vendor's line-up, when it states no count."""

    FLAGSHIP = "flagship"
    SMALL = "small"


@dataclass(frozen=True)
class Fingerprint:
    """What is known about the selected model. Unknown stays None."""

    provider: str
    name: str
    params_b: float | None = None
    vendor: str | None = None
    line: Line | None = None
    # The endpoint answers on this machine: set from the connection's host where
    # the fingerprint is built, never stored, so it follows the connection.
    loopback: bool = False

    @property
    def local(self) -> bool:
        """Whether this model runs on this machine.

        The fallback tier keys on this rather than on the provider's name: a
        hosted endpoint runs models too big for a laptop, a local one runs the
        laptop, and that is a fact about where the endpoint is. The bundled
        runtime has no URL of its own, so it is local by construction.
        """
        return self.provider == "llamacpp" or self.loopback
