"""Redraw: an edit on an image model that takes no picture in. It draws again
from the words the base was drawn with and the change, so Edit works on every
image model; the version says it was drawn again, since it will not keep the
base's composition."""

import asyncio
import io

from PIL import Image, UnidentifiedImageError

from modules.llm.providers.picture_shape import Shape, shape_of
from modules.llm.resolution import ResolvedImageGeneration
from worker.studio.media.visual import EXTENSIONS
from worker.studio.media.visual.edit.base import BaseImage
from worker.studio.media.visual.redraw.drawing_prompt import (
    changed,
    kept_drawing_prompt,
)
from worker.studio.shared.artifact import Built

SAID = "Drawn again with your change."


def render(
    painter: ResolvedImageGeneration, base: BaseImage, instruction: str
) -> Built:
    prompt = changed(base.drawing_prompt, instruction)
    image = asyncio.run(
        painter.generator.generate(painter.selection.name, prompt, shape=_shape(base))
    )
    edited = (
        f"{base.body}\n\nEdited: {instruction}"
        if base.body
        else f"Edited: {instruction}"
    )
    return Built(
        title=base.title,
        markdown=f"{SAID}\n\n{edited}",
        primary=image.content,
        primary_mime=image.media_type,
        primary_filename=f"{base.stem}.{EXTENSIONS[image.media_type]}",
        metadata={**kept_drawing_prompt(prompt), "redrawn": True},
    )


def _shape(base: BaseImage) -> Shape | None:
    try:
        width, height = Image.open(io.BytesIO(base.picture.content)).size
    except (UnidentifiedImageError, OSError):
        return None
    return shape_of(width, height)
