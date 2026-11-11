"""A comic job's options, the kind and how many pictures, checked when it is created."""

from sqlalchemy.orm import Session

from modules.artifacts.comic.kinds import DEFAULT_KIND, KINDS, MAX_PAGES


def validate_options(_session: Session, raw: dict | None) -> dict:
    """The Format hook: raises ValueError naming the option to fix."""
    raw = raw or {}
    kind = raw.get("kind") or DEFAULT_KIND
    if kind not in KINDS:
        raise ValueError(f"kind: choose one of {', '.join(KINDS)}")
    pages = raw.get("pages", KINDS[kind].default_pages)
    if not isinstance(pages, int) or isinstance(pages, bool):
        raise ValueError("pages: give a whole number")
    if not 1 <= pages <= MAX_PAGES:
        raise ValueError(f"pages: from 1 to {MAX_PAGES}")
    return {"kind": kind, "pages": pages}
