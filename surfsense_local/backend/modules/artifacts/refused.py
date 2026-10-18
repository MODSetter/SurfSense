"""A Studio refusal the interface can say in its own words."""

from fastapi import HTTPException


def refused(
    status_code: int, message: str, code: str, **values: str | int
) -> HTTPException:
    """A refusal with a code beside its sentence.

    The interface keys its translated line on the code and falls back to the
    sentence for one it has no line for: studio-error-text.ts, keep them in sync.
    A sentence built from names or numbers sends them raw as ``values``, so the
    interface formats them in its own language.
    """
    return HTTPException(status_code, {"message": message, "code": code, **values})
