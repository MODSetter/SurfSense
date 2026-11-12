"""Comic: the chat model plans it from the sources, the image model draws each
page, and the pages are bound into one PDF in the kind's reading order."""

import asyncio

from modules.artifacts.comic.kinds import KINDS
from modules.llm.pictures_in.model import PictureModel
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.resolution import ResolvedGeneration, ResolvedImageGeneration
from worker.studio.media.visual.comic.asking import ask_for_plan
from worker.studio.media.visual.comic.draw import draw_pages
from worker.studio.media.visual.comic.page_prompt import page_prompt, strip_lines
from worker.studio.media.visual.comic.plan import Plan
from worker.studio.media.visual.comic_binding.bind import BoundPage, bind
from worker.studio.media.visual.drawn.pipeline import DRAWN_FROM_WORDS
from worker.studio.shared.artifact import Built, Source, fallback_title
from worker.studio.shared.text import slug


def render(
    painter: ResolvedImageGeneration,
    writer: ResolvedGeneration,
    sources: list[Source],
    user_prompt: str | None,
    options: dict,
    *,
    keeper: PictureModel | None,
) -> Built:
    kind = KINDS[options["kind"]]
    plan = ask_for_plan(
        writer,
        sources,
        user_prompt,
        kind,
        options["pages"],
        fallback_title(user_prompt, sources, "Comic"),
    )
    # Studio cannot look at a page to check its lettering; a local model's is not
    # measured at all, so its pages are drawn without words and lettered below.
    # Any page drawn locally letters them all so, keeping one comic one way.
    drawers = [painter.selection.provider]
    if keeper is not None and len(plan.pages) > 1:
        drawers.append(keeper.selection.provider)
    lettered = kind.bubbles and sdcpp.PROVIDER not in drawers
    prompts = [
        page_prompt(
            kind,
            plan,
            number,
            lettered=lettered,
            referenced=keeper is not None and number > 1,
        )
        for number in range(1, len(plan.pages) + 1)
    ]
    pictures = asyncio.run(draw_pages(painter, keeper, prompts, kind.shape))
    pdf = bind(
        plan.title,
        [
            BoundPage(picture.content, () if lettered else strip_lines(panels))
            for picture, panels in zip(pictures, plan.pages, strict=True)
        ],
        layout=kind.layout,
        direction=kind.direction,
    )
    metadata: dict = {
        "comic": {"kind": kind.key, "pages": len(plan.pages), "lettered": lettered}
    }
    if keeper is None and len(plan.pages) > 1:
        metadata[DRAWN_FROM_WORDS] = True
    return Built(
        title=plan.title,
        markdown=_markdown(plan, kind.unit),
        primary=pdf,
        primary_mime="application/pdf",
        primary_filename=f"{slug(plan.title, 'comic')}.pdf",
        metadata=metadata,
    )


def _markdown(plan: Plan, unit: str) -> str:
    """Every page's panels and lines, so the comic is found by what it says."""
    parts = [f"# {plan.title}"]
    for number, panels in enumerate(plan.pages, start=1):
        parts.append(f"\n## {unit} {number}\n")
        for index, panel in enumerate(panels, start=1):
            parts.append(f"- Panel {index}: {panel.shows}")
            parts += [f"  - {line}" for line in panel.lines]
    return "\n".join(parts)
