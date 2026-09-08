"""Media artifacts: the audio and visual deliverables.

Podcast is a two-host transcript the model writes, synthesised offline by Kokoro
(tts.py). Image and infographic are drawn over OpenRouter with a BYO key
(visual.py).
"""

from sqlalchemy.orm import Session

from worker.studio import generate
from worker.studio.artifact import Built, Source
from worker.studio.media import visual
from worker.studio.media.podcast import builder as podcast_builder

# Visual formats need a BYO key; podcast runs offline.
_VISUAL = frozenset({"image", "infographic"})
MEDIA: frozenset[str] = _VISUAL | {podcast_builder.key}


def render(
    session: Session, fmt: str, sources: list[Source], prompt: str | None
) -> Built:
    """Produce one media format: a drawn image, or a synthesised podcast."""
    if fmt in _VISUAL:
        return visual.render(session, fmt, sources, prompt)
    # Podcast reuses the builder generation path, then synthesises the transcript.
    raw = generate.generate(session, podcast_builder, sources, prompt)
    return podcast_builder.build(raw, sources)


__all__ = ["MEDIA", "render"]
