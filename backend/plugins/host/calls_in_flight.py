"""The calls running in this copy of the host, so a Stop can end them."""

import hashlib
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager

import anyio

# A token for the user's thread, which the app sends with each call and with its Stop.
CALLS_HEADER = "x-surfsense-calls"


def caller(authorization: str) -> str:
    """Who made a call, as a hash of its sign-in, so no key is kept."""
    return hashlib.sha256(authorization.encode()).hexdigest()


class CallsInFlight:
    def __init__(self) -> None:
        self._running: defaultdict[tuple[str, str], set[anyio.CancelScope]] = (
            defaultdict(set)
        )

    @contextmanager
    def running(self, who: str, token: str) -> Iterator[anyio.CancelScope]:
        scope = anyio.CancelScope()
        self._running[(who, token)].add(scope)
        try:
            yield scope
        finally:
            self._running[(who, token)].discard(scope)
            if not self._running[(who, token)]:
                del self._running[(who, token)]

    def cancel(self, who: str, token: str) -> None:
        """Only the calls of that sign-in and that token: another's are untouched."""
        for scope in self._running.get((who, token), ()):
            scope.cancel()
