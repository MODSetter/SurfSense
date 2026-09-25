"""The running job's cancel check, reachable from deep inside its pipeline.

A context variable rather than a parameter, so no format's pipeline has to
carry it to the one call that waits long enough to need it.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_check: ContextVar[Callable[[], None] | None] = ContextVar(
    "studio_cancel_check", default=None
)


@contextmanager
def watching(raise_if_cancelled: Callable[[], None]) -> Iterator[None]:
    token = _check.set(raise_if_cancelled)
    try:
        yield
    finally:
        _check.reset(token)


def raise_if_cancelled() -> None:
    """Raise the job's own cancel error; a no-op outside a job."""
    check = _check.get()
    if check is not None:
        check()
