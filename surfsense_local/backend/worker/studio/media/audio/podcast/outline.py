from dataclasses import dataclass

from modules.artifacts.podcast.brief import MINUTES, PodcastBrief
from modules.llm import prompting
from modules.llm.profile import Tier
from worker.studio.media.audio.podcast.roster import roster
from worker.studio.shared.text import as_list, as_text, parse_json

# Speaking rate turns the preset into a word budget; segments of ~250 words are
# what a small model drafts well in one reply.
WORDS_PER_MINUTE = 150
WORDS_PER_SEGMENT = 250


@dataclass(frozen=True)
class Segment:
    """One beat of the episode, drafted on its own against the shared plan."""

    title: str
    talking_points: list[str]
    target_words: int


@dataclass(frozen=True)
class Outline:
    title: str
    segments: list[Segment]


def target_words(brief: PodcastBrief) -> int:
    return MINUTES[brief.duration] * WORDS_PER_MINUTE


def prompt(tier: Tier, brief: PodcastBrief, focus: str | None) -> str:
    words = target_words(brief)
    return prompting.load(
        __package__,
        tier,
        case="outline",
        focus=prompting.focus(focus),
        language=brief.language,
        style=brief.style.value,
        roster=roster(brief),
        words=words,
        segments=max(1, round(words / WORDS_PER_SEGMENT)),
    )


def parse(raw: str, brief: PodcastBrief) -> Outline:
    """The plan; untitled segments are dropped, unsized ones share the words evenly."""
    spec = parse_json(raw)
    entries = [
        entry
        for entry in as_list(spec.get("segments"))
        if isinstance(entry, dict) and as_text(entry.get("title"))
    ]
    if not entries:
        raise ValueError("the outline came back without segments")
    even_share = target_words(brief) // len(entries)
    segments = [
        Segment(
            title=as_text(entry["title"]),
            talking_points=[as_text(p) for p in as_list(entry.get("talking_points"))],
            target_words=_words(entry.get("target_words"), even_share),
        )
        for entry in entries
    ]
    return Outline(as_text(spec.get("title")) or "Podcast", segments)


def _words(value: object, fallback: int) -> int:
    return value if isinstance(value, int) and value > 0 else fallback
