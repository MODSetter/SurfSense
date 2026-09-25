import logging
from dataclasses import dataclass

from modules.artifacts.podcast.brief import PodcastBrief
from modules.llm import prompting
from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration
from worker.studio.media.audio.podcast.outline import WORDS_PER_SEGMENT, Segment
from worker.studio.media.audio.podcast.roster import roster
from worker.studio.shared import generate
from worker.studio.shared.artifact import Source
from worker.studio.shared.text import as_list, as_text, parse_json

logger = logging.getLogger(__name__)

# How much of the dialogue so far each segment sees, so it continues rather
# than restarts, without carrying the whole episode in every call.
RECAP_CHARS = 800
# A segment's JSON measured 2.5 tokens a word in English and 5.5 in Hindi on
# Qwen3's tokenizer; 12 lets a reply run past twice its target and stops a loop
# in seconds. The target is the outline's guess, once 20 words, so it never
# counts under a planned segment.
REPLY_TOKENS_PER_WORD = 12
_JSON_NUDGE = "Your previous reply was not valid JSON. Return only the JSON object."


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
        text = prompt(
            model.tier, brief, segment, position, len(segments), recap(turns, brief)
        )
        turns.extend(
            _draft_one(
                model,
                brief,
                text,
                position,
                len(segments),
                sources,
                max_tokens=max(segment.target_words, WORDS_PER_SEGMENT)
                * REPLY_TOKENS_PER_WORD,
            )
        )
    return turns


def prompt(
    tier: Tier,
    brief: PodcastBrief,
    segment: Segment,
    position: int,
    total: int,
    recap: str | None,
) -> str:
    return prompting.load(
        __package__,
        tier,
        case="draft",
        language=brief.language,
        style=brief.style.value,
        roster=roster(brief),
        continuity=_continuity(recap),
        position=position,
        total=total,
        title=segment.title,
        points="\n".join(f"- {point}" for point in segment.talking_points),
        target_words=segment.target_words,
    )


def _continuity(recap: str | None) -> str:
    """Where the segment picks up, so the dialogue continues rather than restarts."""
    if not recap:
        return "This is the opening segment; begin the conversation naturally."
    return (
        "Recap of the conversation so far — continue from here, do not repeat it:\n"
        f"{recap}"
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
    *,
    max_tokens: int,
) -> list[Turn]:
    reply = generate.run_model(model, text, sources, max_tokens=max_tokens)
    try:
        return parse(reply, brief)
    except ValueError as first:
        logger.warning(
            "studio: podcast segment %s/%s: %s; retrying", position, total, first
        )
    retry = generate.run_model(
        model,
        text,
        sources,
        repair=generate.Repair(reply, _JSON_NUDGE),
        max_tokens=max_tokens,
    )
    try:
        return parse(retry, brief)
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
