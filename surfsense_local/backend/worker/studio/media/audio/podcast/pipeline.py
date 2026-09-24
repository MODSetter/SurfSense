import asyncio
import logging

from modules.artifacts.podcast.brief import PodcastBrief
from modules.llm.providers.protocols import SpokenTurn, TextToSpeech
from modules.llm.resolution import ResolvedGeneration
from worker.studio.media.audio.podcast import draft, outline
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import slug

logger = logging.getLogger(__name__)

_EXTENSIONS = {"audio/wav": "wav", "audio/mpeg": "mp3", "audio/ogg": "ogg"}
# Fewer lines than this is not an episode; voicing it would waste CPU minutes.
MIN_TURNS = 2


def render(
    model: ResolvedGeneration,
    voice: TextToSpeech,
    sources: list[Source],
    user_prompt: str | None,
    options: dict,
) -> Built:
    """Plan the episode, draft it segment by segment, then voice every line."""
    brief = PodcastBrief.model_validate(options)

    plan = outline.parse(
        generate.run_model(
            model, outline.prompt(model.tier, brief, user_prompt), sources
        ),
        brief,
    )
    turns = draft.draft(model, brief, plan.segments, sources)
    if len(turns) < MIN_TURNS:
        raise ValueError("the episode came back too short to voice")

    spoken = [SpokenTurn(brief.speakers[t.speaker - 1].voice, t.text) for t in turns]
    logger.info(
        "studio: podcast %r: %s segments, %s turns (%s spoken chars); synthesising",
        plan.title,
        len(plan.segments),
        len(spoken),
        sum(len(turn.text) for turn in spoken),
    )
    audio = asyncio.run(voice.synthesize(spoken, brief.language))
    return Built(
        title=plan.title,
        markdown=_transcript(plan.title, brief, turns),
        primary=audio.content,
        primary_mime=audio.media_type,
        primary_filename=f"{slug(plan.title, 'podcast')}."
        f"{_EXTENSIONS.get(audio.media_type, 'bin')}",
    )


def _transcript(title: str, brief: PodcastBrief, turns: list[draft.Turn]) -> str:
    cast = ", ".join(f"{s.name} ({s.role.value})" for s in brief.speakers)
    lines = [f"# {title}", "", f"_{cast}_", ""]
    for turn in turns:
        lines += [f"**{brief.speakers[turn.speaker - 1].name}:** {turn.text}", ""]
    return "\n".join(lines).strip()
