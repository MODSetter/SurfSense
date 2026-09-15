import logging
from dataclasses import dataclass

from modules.artifacts.podcast.brief import PodcastBrief
from modules.llm.resolution import ResolvedGeneration
from worker.studio.media.audio.podcast.outline import Segment
from worker.studio.media.audio.podcast.roster import roster
from worker.studio.shared import generate
from worker.studio.shared.artifact import Source
from worker.studio.shared.text import as_list, as_text, parse_json

logger = logging.getLogger(__name__)

# How much of the dialogue so far each segment sees, so it continues rather
# than restarts, without carrying the whole episode in every call.
RECAP_CHARS = 800
_JSON_NUDGE = "\nYour previous reply was not valid JSON. Return only the JSON object."


@dataclass(frozen=True)
class Turn:
    """One spoken line, attributed to a cast slot (1-based, as the roster)."""

    speaker: int
    text: str


def draft(
    model: ResolvedGeneration,
    brief: PodcastBrief,
    segments: list[Segment],
    sources: list[Source],
) -> list[Turn]:
    """Every segment in order, each drafted with a recap of the ones before."""
    turns: list[Turn] = []
    for position, segment in enumerate(segments, start=1):
        text = prompt(brief, segment, position, len(segments), recap(turns, brief))
        turns.extend(_draft_one(model, brief, text, position, len(segments), sources))
    return turns


def prompt(
    brief: PodcastBrief, segment: Segment, position: int, total: int, recap: str | None
) -> str:
    continuity = (
        f"\nRecap of the conversation so far (continue from here, do not repeat it):"
        f"\n{recap}\n"
        if recap
        else "\nThis is the opening segment; begin the conversation naturally.\n"
    )
    points = "\n".join(f"- {point}" for point in segment.talking_points)
    return (
        f"You are scripting natural podcast dialogue for segment {position} of "
        f"{total}. Write entirely in {brief.language}. The format is "
        f"{brief.style.value}.\nSpeakers, attribute every line by number:\n"
        f"{roster(brief)}\n{continuity}\n"
        f'This segment is "{segment.title}". Cover these points using only facts '
        f"from the sources:\n{points}\n"
        f"Aim for about {segment.target_words} words of dialogue. Keep turns short "
        "and varied; speakers react to each other rather than deliver monologues. "
        "No greetings or sign-offs unless this is the first or last segment.\n"
        'Return only JSON, no prose: {"turns": [{"speaker": int, "text": str}]}'
    )


def parse(raw: str, brief: PodcastBrief) -> list[Turn]:
    """The segment's lines, each mapped to a cast member; lines for nobody drop."""
    by_name = {
        speaker.name.lower(): slot for slot, speaker in enumerate(brief.speakers, 1)
    }
    turns = []
    for entry in as_list(parse_json(raw).get("turns")):
        if not isinstance(entry, dict):
            continue
        slot = _slot(entry.get("speaker"), by_name)
        text = as_text(entry.get("text"))
        if slot is not None and text:
            turns.append(Turn(slot, text))
    if not turns:
        raise ValueError("the segment came back without dialogue")
    return turns


def recap(turns: list[Turn], brief: PodcastBrief) -> str | None:
    if not turns:
        return None
    lines = "\n".join(f"{brief.speakers[t.speaker - 1].name}: {t.text}" for t in turns)
    return lines[-RECAP_CHARS:]


def _draft_one(
    model: ResolvedGeneration,
    brief: PodcastBrief,
    text: str,
    position: int,
    total: int,
    sources: list[Source],
) -> list[Turn]:
    try:
        return parse(generate.run_model(model, text, sources), brief)
    except ValueError as first:
        logger.warning(
            "studio: podcast segment %s/%s: %s; retrying", position, total, first
        )
    try:
        return parse(generate.run_model(model, text + _JSON_NUDGE, sources), brief)
    except ValueError as error:
        raise ValueError(
            f"Segment {position} of {total} could not be drafted: {error}"
        ) from error


def _slot(value: object, by_name: dict[str, int]) -> int | None:
    """Accepts the slot number, the number as text, or the speaker's name."""
    text = as_text(value)
    if text.isdigit():
        slot = int(text)
        return slot if 1 <= slot <= len(by_name) else None
    return by_name.get(text.lower())
