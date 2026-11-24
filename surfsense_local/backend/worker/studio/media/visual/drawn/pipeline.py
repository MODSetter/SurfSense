"""Drawn: the prompt the agent wrote goes to the image model as written.

No chat model rewrites it: the agent has already read what the picture draws on.
With reference pictures it goes to the model that takes pictures, so a comic's
pages keep their characters; with none, it is drawn from the words alone.
"""

import asyncio

from modules.llm.pictures_in.model import PictureModel
from modules.llm.providers.picture_shape import Shape
from modules.llm.providers.protocols import GeneratedImage
from modules.llm.resolution import ResolvedImageGeneration
from worker.studio.media.visual import EXTENSIONS
from worker.studio.media.visual.infographic.style import in_infographic_style
from worker.studio.media.visual.redraw.drawing_prompt import kept_drawing_prompt
from worker.studio.shared.artifact import Built
from worker.studio.shared.text import slug

# Kept on a version whose references no chosen model could take.
DRAWN_FROM_WORDS = "drawn_from_words"


def render(
    painter: ResolvedImageGeneration,
    prompt: str,
    title: str,
    format: str,
    *,
    shape: Shape | None = None,
    references: tuple[GeneratedImage, ...] = (),
    keeper: PictureModel | None = None,
) -> Built:
    painted = in_infographic_style(prompt) if format == "infographic" else prompt
    metadata = kept_drawing_prompt(painted)
    if references and keeper is not None:
        image = asyncio.run(
            keeper.editor.edit(keeper.selection.name, painted, references, shape=shape)
        )
    else:
        image = asyncio.run(
            painter.generator.generate(painter.selection.name, painted, shape=shape)
        )
        if references:
            metadata[DRAWN_FROM_WORDS] = True
    return Built(
        title=title,
        markdown=f"# {title}\n\n{prompt}",
        primary=image.content,
        primary_mime=image.media_type,
        primary_filename=f"{slug(title, format)}.{EXTENSIONS[image.media_type]}",
        metadata=metadata,
    )
