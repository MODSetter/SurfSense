"""Refuse deleting a version alone while a later edit starts from it.

The edit's recipe names its base rather than copying its bytes, so its Retry
would have no picture. The app deletes a document's versions newest first.
"""

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.artifacts.image_edits.recipe import IMAGE_EDIT
from modules.artifacts.models import Artifact
from modules.artifacts.refused import refused
from modules.artifacts.studio_documents.recipe import RECIPE_KEY


def refuse_deleting_a_base(session: Session, artifact_id: int) -> None:
    recipe = Artifact.artifact_metadata[RECIPE_KEY]
    edit = session.scalar(
        select(Artifact.id)
        .where(
            recipe["kind"].as_string() == IMAGE_EDIT,
            recipe["base_artifact_id"].as_integer() == artifact_id,
        )
        .limit(1)
    )
    if edit is not None:
        raise refused(
            status.HTTP_409_CONFLICT,
            "A later version is edited from this one: delete the whole document.",
            "edited_from",
        )
