"""Registry of the stable identities a user can be recognised by."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, NamedTuple

from .fingerprint import fingerprint


class Identity(NamedTuple):
    kind: str
    fingerprint: str


IdentityExtractor = Callable[[Any], Iterable[str]]

_SOURCES: dict[str, IdentityExtractor] = {}


def identity_source(kind: str) -> Callable[[IdentityExtractor], IdentityExtractor]:
    """Register an extractor for one kind of identity. Raises on duplicate kind."""

    def register(extract: IdentityExtractor) -> IdentityExtractor:
        if kind in _SOURCES:
            raise ValueError(f"Identity source already registered: {kind!r}")
        _SOURCES[kind] = extract
        return extract

    return register


def identities_of(user: Any) -> list[Identity]:
    """Every identity a user presents, deduplicated."""
    identities: list[Identity] = []

    for kind, extract in _SOURCES.items():
        for value in extract(user):
            identity = Identity(kind, fingerprint(value))
            if identity not in identities:
                identities.append(identity)

    return identities
