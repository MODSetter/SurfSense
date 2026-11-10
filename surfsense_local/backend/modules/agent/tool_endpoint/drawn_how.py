"""Where a picture was drawn, and how when not as asked, for the agent to act on:
a comic draws wordless pages on this computer, and says when faces may differ."""

from sqlalchemy.orm import Session

from modules.artifacts.drawn_images.recipe import image_drawing_of
from modules.artifacts.image_edits.recipe import image_edit_of
from modules.artifacts.models import Artifact
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.pictures_in import model as pictures_in
from modules.llm.providers.sdcpp import provider as sdcpp

REDRAWN = (
    "Drawn again from its prompt and the change: this image model takes no picture "
    "in, so it may not keep the rest of the picture."
)
FROM_WORDS = (
    "Drawn from words alone: this image model takes no picture in, so the "
    "characters may differ from the references."
)


def drawn_how(session: Session, artifact: Artifact) -> list[str]:
    meta = artifact.artifact_metadata or {}
    redrawn, from_words = bool(meta.get("redrawn")), bool(meta.get("drawn_from_words"))
    drawing = image_drawing_of(meta)
    took_pictures = not (redrawn or from_words) and (
        image_edit_of(meta) is not None
        or (drawing is not None and bool(drawing.references))
    )
    lines = [_where(session, took_pictures)]
    if redrawn:
        lines.append(REDRAWN)
    if from_words:
        lines.append(FROM_WORDS)
    return [line for line in lines if line]


def _where(session: Session, took_pictures: bool) -> str:
    slot = (
        ModelType.IMAGE_EDIT
        if took_pictures and pictures_in.picture_source(session) == "edit_model"
        else ModelType.IMAGE_GEN
    )
    selected = session.get(SelectedModel, slot)
    if selected is None:
        return ""
    if selected.provider == sdcpp.PROVIDER:
        return "Drawn on this computer."
    connection = (
        session.get(ProviderConnection, selected.connection_id)
        if selected.connection_id is not None
        else None
    )
    return f"Drawn by {connection.label}." if connection is not None else ""
