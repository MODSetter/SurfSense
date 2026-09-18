"""Image: the chat model names the piece and writes the image prompt from the
sources; the image model paints that prompt."""

import asyncio

from modules.llm import prompting
from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration, ResolvedImageGeneration
from worker.studio.media.visual import EXTENSIONS
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source, fallback_title
from worker.studio.shared.text import as_text, parse_json, slug


def render(
    painter: ResolvedImageGeneration,
    writer: ResolvedGeneration,
    sources: list[Source],
    user_prompt: str | None,
) -> Built:
    spec = parse_json(
        generate.run_model(writer, prompt(writer.tier, user_prompt), sources)
    )
    image_prompt = as_text(spec.get("prompt"))
    if not image_prompt:
        raise ValueError("the writer returned no image prompt")
    title = as_text(spec.get("title")) or fallback_title(user_prompt, sources, "Image")

    image = asyncio.run(
        painter.generator.generate(painter.selection.name, image_prompt)
    )
    return Built(
        title=title,
        markdown=f"# {title}\n\n{image_prompt}",
        primary=image.content,
        primary_mime=image.media_type,
        primary_filename=f"{slug(title, 'image')}.{EXTENSIONS[image.media_type]}",
    )


def prompt(tier: Tier, user_prompt: str | None) -> str:
    return prompting.load(__package__, tier, focus=prompting.focus(user_prompt))
