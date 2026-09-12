import asyncio

from sqlalchemy.orm import Session

from modules.llm.resolution import ModelResolutionError, resolve_image_generation
from worker.studio.artifact import Built, Source

GROUNDING_CHARS = 6_000
_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}


def render(
    session: Session, sources: list[Source], user_prompt: str | None
) -> Built:
    try:
        resolved = resolve_image_generation(session)
    except ModelResolutionError as error:
        raise RuntimeError(str(error)) from error

    instruction = "Create a single illustrative image grounded in the sources below."
    if user_prompt:
        instruction += f" Emphasise: {user_prompt}."
    grounding = "\n\n".join(
        f"{source.title}: {source.content}" for source in sources
    )[:GROUNDING_CHARS]
    image = asyncio.run(
        resolved.generator.generate(
            resolved.selection.name, f"{instruction}\n\n{grounding}"
        )
    )
    title = (user_prompt or "Image").strip()[:200] or "Image"
    extension = _EXTENSIONS[image.media_type]
    return Built(
        title=title,
        markdown=f"# {title}\n\n{instruction}",
        primary=image.content,
        primary_mime=image.media_type,
        primary_filename=f"image.{extension}",
    )
