"""Image: the chat model names the piece and writes the image prompt from the
sources; the image model paints that prompt."""

import asyncio

from modules.llm.resolution import ResolvedGeneration, ResolvedImageGeneration
from worker.studio.media.visual import EXTENSIONS
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source, fallback_title
from worker.studio.shared.text import as_text, parse_json, slug

_SCHEMA = (
    'Return only JSON, no prose: {"title": str, "prompt": str}. The title names '
    "the image in a few words. The prompt is a single self-contained paragraph an "
    "image model paints from: subject, composition, lighting, style; no text to "
    "render, no source names."
)


def render(
    painter: ResolvedImageGeneration,
    writer: ResolvedGeneration,
    sources: list[Source],
    user_prompt: str | None,
) -> Built:
    spec = parse_json(generate.run_model(writer, _brief_prompt(user_prompt), sources))
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


def _brief_prompt(user_prompt: str | None) -> str:
    focus = f" Emphasise: {user_prompt}." if user_prompt else ""
    return (
        f"Design one illustrative image grounded in the sources below.{focus} {_SCHEMA}"
    )
