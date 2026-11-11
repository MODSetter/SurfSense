"""A picture drawn as a comic's page: kept for the agent, never listed apart from its comic."""

from typing import Any

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact

COMIC_PAGE = "comic_page"


def is_comic_page(metadata: dict[str, Any] | None) -> bool:
    return bool((metadata or {}).get(COMIC_PAGE))


def mark_comic_pages(session: Session, picture_ids: list[int]) -> None:
    """Marked again when bound, for a page the agent drew without the mark."""
    for picture_id in picture_ids:
        picture = session.get(Artifact, picture_id)
        if picture is not None and not is_comic_page(picture.artifact_metadata):
            picture.artifact_metadata = {
                **(picture.artifact_metadata or {}),
                COMIC_PAGE: True,
            }
