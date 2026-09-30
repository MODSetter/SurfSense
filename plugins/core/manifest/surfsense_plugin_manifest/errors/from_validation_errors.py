"""Pydantic's errors, rewritten as the lines an author reads in a review."""

from pydantic import ValidationError


def errors_from(error: ValidationError) -> list[str]:
    return [f"{_where(e['loc'])}: {_why(e)}" for e in error.errors()]


def _where(location: tuple[str | int, ...]) -> str:
    path = ""
    for part in location:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path.removeprefix(".")


def _why(error: dict) -> str:
    context = error.get("ctx") or {}
    # Our own rules raise ValueError; its text is written for authors already.
    if "error" in context:
        return str(context["error"])
    if error["type"] == "literal_error":
        return "must be " + context["expected"].replace("'", "")
    if error["type"] == "missing":
        return "is required"
    if error["type"] == "too_short":
        return "must not be empty"
    return error["msg"]
