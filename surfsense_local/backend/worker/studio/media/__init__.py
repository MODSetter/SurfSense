"""Media artifacts: generated images and offline podcast audio."""

import logging

from sqlalchemy.orm import Session

from worker.studio import generate
from worker.studio.artifact import Built, Source
from worker.studio.media import image
from worker.studio.media.podcast import builder as podcast_builder

logger = logging.getLogger(__name__)

_VISUAL = frozenset({"image"})
MEDIA: frozenset[str] = _VISUAL | {podcast_builder.key}


def render(
    session: Session, fmt: str, sources: list[Source], prompt: str | None
) -> Built:
    """Produce one media format: a drawn image, or a synthesised podcast."""
    if fmt in _VISUAL:
        logger.info("studio: media %s drawing", fmt)
        return image.render(session, sources, prompt)
    # Podcast reuses the builder generation path, then synthesises the transcript.
    logger.info("studio: media podcast asking the model for a transcript")
    raw = generate.generate(session, podcast_builder, sources, prompt)
    logger.info("studio: media podcast transcript %s chars; synthesising", len(raw))
    return podcast_builder.build(raw, sources)


__all__ = ["MEDIA", "render"]
