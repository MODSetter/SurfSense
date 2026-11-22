"""The pages that go with a deleted comic: those no other comic binds and no document places.

A page is never listed, so nothing else would remove it. Every version of a page
goes with it, newest first, since an edit names the version it was made from.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.artifacts.comic.binding_recipe import comic_binding_of
from modules.artifacts.comic.pages import is_comic_page
from modules.artifacts.models import Artifact
from modules.artifacts.script_documents.spec import DOCUMENT_FORMATS, document_script
from modules.artifacts.script_documents.version import version_of


def unused_pages(session: Session, comic: Artifact) -> list[Artifact]:
    binding = comic_binding_of(comic.artifact_metadata)
    if binding is None:
        return []
    still_used = _used_elsewhere(session, comic)
    gone: dict[int, Artifact] = {}
    for page in binding.pages:
        picture = session.get(Artifact, page.picture)
        if picture is None or not is_comic_page(picture.artifact_metadata):
            continue
        versions = _versions(session, picture)
        if any(version.id in still_used for version in versions):
            continue
        gone.update({version.id: version for version in versions})
    return sorted(gone.values(), key=lambda artifact: artifact.id, reverse=True)


def _used_elsewhere(session: Session, comic: Artifact) -> set[int]:
    """Pictures another comic binds, or a document of the workspace places."""
    others = session.scalars(
        select(Artifact).where(
            Artifact.workspace_id == comic.workspace_id,
            Artifact.id != comic.id,
            Artifact.format.in_(("comic", *DOCUMENT_FORMATS)),
        )
    )
    used: set[int] = set()
    for other in others:
        binding = comic_binding_of(other.artifact_metadata)
        if binding is not None:
            used.update(page.picture for page in binding.pages)
        script = document_script(other.artifact_metadata)
        if script is not None:
            used.update(
                int(name.removeprefix("image-"))
                for name in script.images
                if name.removeprefix("image-").isdigit()
            )
    return used


def _versions(session: Session, picture: Artifact) -> list[Artifact]:
    """Every comic page in the picture's line of versions, or the picture alone."""
    version = version_of(picture.artifact_metadata)
    if version is None:
        return [picture]
    siblings = session.scalars(
        select(Artifact).where(
            Artifact.workspace_id == picture.workspace_id,
            Artifact.chat_thread_id == picture.chat_thread_id,
            Artifact.format == picture.format,
        )
    )
    return [
        sibling
        for sibling in siblings
        if is_comic_page(sibling.artifact_metadata)
        and (found := version_of(sibling.artifact_metadata)) is not None
        and found.root == version.root
    ] or [picture]
