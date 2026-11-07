"""Infographic: the chat model writes a factual brief, the image model paints it.

Distilling first keeps the picture grounded and gives the image model the short
prompt it draws well from.
"""

import asyncio

from modules.llm import prompting
from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration, ResolvedImageGeneration
from worker.studio.media.visual import EXTENSIONS
from worker.studio.media.visual.infographic.style import in_infographic_style
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source, fallback_title
from worker.studio.shared.text import as_list, as_text, parse_json, slug

# The frontier prompt leaves the count to the material, so the ceiling is kept
# here: past this a drawn panel stops being readable.
SECTIONS = 8


def render(
    painter: ResolvedImageGeneration,
    writer: ResolvedGeneration,
    sources: list[Source],
    user_prompt: str | None,
) -> Built:
    brief = _brief(
        generate.run_model(writer, prompt(writer.tier, user_prompt), sources),
        fallback_title(user_prompt, sources, "Infographic"),
    )
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


def prompt(tier: Tier, user_prompt: str | None) -> str:
    return prompting.load(
        __package__, tier, focus=prompting.focus(user_prompt), ceiling=SECTIONS
    )


def _brief(raw: str, untitled: str) -> Brief:
    spec = parse_json(raw)
    sections = [
        (
            as_text(section.get("label"))[:60],
            as_text(section.get("value"))[:80],
            as_text(section.get("detail")),
        )
        for section in as_list(spec.get("sections"))[:SECTIONS]
        if isinstance(section, dict)
    ]
    return (
        as_text(spec.get("title")) or untitled,
        as_text(spec.get("summary")),
        sections,
    )


def _image_prompt(brief: Brief) -> str:
    title, summary, sections = brief
    facts = "\n".join(
        f"- {label}: {value}. {detail}" for label, value, detail in sections
    )
    return in_infographic_style(f"{title}\n{summary}\n{facts}")


def _markdown(brief: Brief) -> str:
    title, summary, sections = brief
    lines = [f"# {title}"] + ([summary] if summary else [])
    for label, value, detail in sections:
        lines.append(f"\n## {label}\n\n**{value}**\n\n{detail}")
    return "\n".join(lines)
