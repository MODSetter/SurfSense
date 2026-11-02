"""Edit: the instruction and the base's picture go to the edit model as written.

No chat model rewrites the instruction first: that would add a call, and a
wait for the chat model, to every edit.
"""

import asyncio

from modules.llm.resolution import ResolvedImageEdit
from worker.studio.media.visual import EXTENSIONS
from worker.studio.media.visual.edit.base import BaseImage
from worker.studio.shared.artifact import Built


def render(editor: ResolvedImageEdit, base: BaseImage, instruction: str) -> Built:
    image = asyncio.run(
        editor.editor.edit(editor.selection.name, instruction, base.picture)
    )
    # The base's body still says what the picture shows; the line says how it moved.
    body = (
        f"{base.body}\n\nEdited: {instruction}"
        if base.body
        else f"Edited: {instruction}"
    )
    return Built(
        title=base.title,
        markdown=body,
        primary=image.content,
        primary_mime=image.media_type,
        primary_filename=f"{base.stem}.{EXTENSIONS[image.media_type]}",
    )
