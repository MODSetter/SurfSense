import asyncio

from modules.llm.resolution import ResolvedImageGeneration
from worker.studio.media.visual import EXTENSIONS
from worker.studio.shared.artifact import Built, Source

GROUNDING_CHARS = 6_000


def render(
    model: ResolvedImageGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    instruction = "Create a single illustrative image grounded in the sources below."
    if user_prompt:
        instruction += f" Emphasise: {user_prompt}."
    grounding = "\n\n".join(f"{source.title}: {source.content}" for source in sources)[
        :GROUNDING_CHARS
    ]
    image = asyncio.run(
        model.generator.generate(model.selection.name, f"{instruction}\n\n{grounding}")
    )
    title = (user_prompt or "Image").strip()[:200] or "Image"
    extension = EXTENSIONS[image.media_type]
    return Built(
        title=title,
        markdown=f"# {title}\n\n{instruction}",
        primary=image.content,
        primary_mime=image.media_type,
        primary_filename=f"image.{extension}",
    )
