"""What a redraw starts from, for pictures made before their prompt was kept."""

import pytest

from modules.artifacts.models import Artifact
from modules.documents.models import Document
from worker.studio.media.visual.infographic.style import in_infographic_style
from worker.studio.media.visual.redraw.drawing_prompt import drawing_prompt_of

pytestmark = pytest.mark.unit


def _older(fmt: str) -> Artifact:
    """No `drawing_prompt` and no recipe: only the body Studio wrote under its title."""
    document = Document(title="Saturn", content="# Saturn\n\nRings: 7 main rings")
    return Artifact(format=fmt, artifact_metadata={}, document=document)


def test_an_older_infographic_is_redrawn_in_studios_style() -> None:
    """Its body is the brief alone; the style it was drawn in is not in it."""
    assert drawing_prompt_of(_older("infographic")) == in_infographic_style(
        "Rings: 7 main rings"
    )


def test_an_older_image_is_redrawn_from_its_body_as_written() -> None:
    """An image's body is the prompt it was drawn from."""
    assert drawing_prompt_of(_older("image")) == "Rings: 7 main rings"
