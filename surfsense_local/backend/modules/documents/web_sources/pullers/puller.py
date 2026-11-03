from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple
from urllib.parse import SplitResult

# Called with each host before a read connects to it: returns when the user
# allowed it, raises EgressDeniedError when not.
HostCheck = Callable[[str], None]


class Pulled(NamedTuple):
    title: str
    markdown: str


@dataclass(frozen=True)
class Puller:
    # Stored on the note, and shown on a result row.
    id: str
    takes: Callable[[SplitResult], bool]
    # The hosts a read of the link starts on: what Add asks the user about.
    hosts: Callable[[str], list[str]]
    # Raises ReadFailedError, or EgressDeniedError for a host turned off.
    read: Callable[[str, HostCheck], Pulled]
