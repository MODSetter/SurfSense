"""Every manifest model forbids fields it does not declare, so a typo fails the
load instead of being ignored."""

from pydantic import ConfigDict

STRICT = ConfigDict(extra="forbid", frozen=True)
