"""Infographic: the chat model writes a factual brief, the image model paints it.

Distilling first keeps the picture grounded and gives the image model the short
prompt it draws well from.
"""

import asyncio

from modules.llm.resolution import ResolvedGeneration, ResolvedImageGeneration
from worker.studio.media.visual import EXTENSIONS
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import as_list, as_text, parse_json, slug

_SCHEMA = (
    'Return only JSON, no prose: {"title": str, "summary": str, "sections": '
    '[{"label": str, "value": str, "detail": str}]}. Use at most 6 sections. '
    "Keep every value factual and grounded in the supplied sources."
)
_TASK = (
    "Create a polished, complete infographic from the supplied factual source. "
    "Choose the clearest visual hierarchy and composition. Summarize or omit "
    "secondary detail when necessary for readability. Keep all important content "
    "fully visible within the canvas, preserve factual accuracy, and follow the "
    "selected visual style."
)
# ponytail: one style for now. A picker rides on the job's `options` once the
# panel offers one.
_STYLE = (
    "Use a hand-drawn editorial sketchnote style with mostly black ink on a warm "
    "white background, one restrained accent color, simple icons, arrows, "
    "connectors, loose organic lines, generous whitespace, short hand-lettered "
    "headings, and highly legible labels. Avoid photorealism, dense paragraphs, "
    "decorative illegible handwriting, and watermarks."
)


def render(
    painter: ResolvedImageGeneration,
    writer: ResolvedGeneration,
    sources: list[Source],
    user_prompt: str | None,
) -> Built:
    brief = _brief(generate.run_model(writer, _brief_prompt(user_prompt), sources))
    image = asyncio.run(
        painter.generator.generate(painter.selection.name, _image_prompt(brief))
    )
    title = brief[0]
    return Built(
        title=title,
        markdown=_markdown(brief),
        primary=image.content,
        primary_mime=image.media_type,
        primary_filename=f"{slug(title, 'infographic')}.{EXTENSIONS[image.media_type]}",
    )


Brief = tuple[str, str, list[tuple[str, str, str]]]  # title, summary, sections


def _brief_prompt(user_prompt: str | None) -> str:
    focus = f" Emphasise: {user_prompt}." if user_prompt else ""
    return (
        "Create the structured content for a concise factual infographic from "
        f"the sources below.{focus} {_SCHEMA}"
    )


def _brief(raw: str) -> Brief:
    spec = parse_json(raw)
    sections = [
        (
            as_text(section.get("label"))[:60],
            as_text(section.get("value"))[:80],
            as_text(section.get("detail")),
        )
        for section in as_list(spec.get("sections"))[:6]
        if isinstance(section, dict)
    ]
    return (
        as_text(spec.get("title")) or "Infographic",
        as_text(spec.get("summary")),
        sections,
    )


def _image_prompt(brief: Brief) -> str:
    title, summary, sections = brief
    facts = "\n".join(
        f"- {label}: {value}. {detail}" for label, value, detail in sections
    )
    content = f"{title}\n{summary}\n{facts}"
    return f"{_TASK}\n\nCONTENT\n{content}\n\nVISUAL STYLE\n{_STYLE}"


def _markdown(brief: Brief) -> str:
    title, summary, sections = brief
    lines = [f"# {title}"] + ([summary] if summary else [])
    for label, value, detail in sections:
        lines.append(f"\n## {label}\n\n**{value}**\n\n{detail}")
    return "\n".join(lines)
