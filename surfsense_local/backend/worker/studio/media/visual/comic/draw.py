"""Page 1 alone, then every later page with page 1 as its reference, so the cast stays the same."""

import asyncio
from collections.abc import Awaitable

from modules.llm.pictures_in.model import PictureModel
from modules.llm.providers.protocols import GeneratedImage
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.resolution import ResolvedImageGeneration


async def draw_pages(
    painter: ResolvedImageGeneration,
    keeper: PictureModel | None,
    prompts: list[str],
    shape: str,
) -> list[GeneratedImage]:
    first = await painter.generator.generate(
        painter.selection.name, prompts[0], shape=shape
    )

    def page(prompt: str) -> Awaitable[GeneratedImage]:
        if keeper is None:
            return painter.generator.generate(
                painter.selection.name, prompt, shape=shape
            )
        return keeper.editor.edit(keeper.selection.name, prompt, (first,), shape=shape)

    rest = prompts[1:]
    # A remote model draws the later pages side by side; this computer's, one at a time.
    if _on_this_computer(painter, keeper):
        drawn = [await page(prompt) for prompt in rest]
    else:
        drawn = list(await asyncio.gather(*(page(prompt) for prompt in rest)))
    return [first, *drawn]


def _on_this_computer(
    painter: ResolvedImageGeneration, keeper: PictureModel | None
) -> bool:
    return painter.selection.provider == sdcpp.PROVIDER or (
        keeper is not None and keeper.selection.provider == sdcpp.PROVIDER
    )
