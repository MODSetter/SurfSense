"""What a person names for every curated model, whichever engine runs it."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entry:
    id: str
    name: str
    family: str
    publisher: str
    description: str
    license: str
    source_repo: str
    # Where the builds come from: an ungated mirror is preferred over a gated
    # vendor repo, with the vendor recorded as `upstream_repo`.
    repo: str
    upstream_repo: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
