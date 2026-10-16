"""A Studio refusal the interface can say in its own words."""

from fastapi import HTTPException


def refused(status_code: int, message: str, code: str) -> HTTPException:
    """A refusal with a code beside its sentence.

    The interface keys its translated line on the code and falls back to the
    sentence for one it has no line for: studio-error-text.ts, keep them in sync.
    """
    return HTTPException(status_code, {"message": message, "code": code})
