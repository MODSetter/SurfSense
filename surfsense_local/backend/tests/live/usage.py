"""Tokens one or more model calls used, as the provider reported them."""

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            *(getattr(self, f.name) + getattr(other, f.name) for f in fields(Usage))
        )
