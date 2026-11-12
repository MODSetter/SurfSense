"""Which model a picture goes to, for the app: an edit, or a redraw when none."""

from fastapi import APIRouter
from pydantic import BaseModel

from api.dependencies import SessionDep
from modules.llm.pictures_in.model import PictureSource, picture_source

router = APIRouter(prefix="/llm", tags=["llm"])


class PicturesInRead(BaseModel):
    # None: every change to a picture is drawn again from its prompt.
    source: PictureSource | None


@router.get(
    "/pictures-in",
    response_model=PicturesInRead,
    summary="Which chosen model takes a picture in, if any",
)
def read_pictures_in(session: SessionDep) -> PicturesInRead:
    return PicturesInRead(source=picture_source(session))
