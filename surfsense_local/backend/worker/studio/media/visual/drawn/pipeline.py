"""Drawn: the prompt the agent wrote goes to the image model as written.

No chat model rewrites it: the agent has already read what the picture draws on.
"""

import asyncio

from modules.llm.resolution import ResolvedImageGeneration
from worker.studio.media.visual import EXTENSIONS
from worker.studio.media.visual.infographic.style import in_infographic_style
from worker.studio.shared.artifact import Built
from worker.studio.shared.text import slug


def render(
    painter: ResolvedImageGeneration, prompt: str, title: str, format: str
) -> Built:
    painted = in_infographic_style(prompt) if format == "infographic" else prompt
    image = asyncio.run(painter.generator.generate(painter.selection.name, painted))
    return Built(
        title=title,
        markdown=f"# {title}\n\n{prompt}",
        primary=image.content,
        primary_mime=image.media_type,
        primary_filename=f"{slug(title, format)}.{EXTENSIONS[image.media_type]}",
    )
