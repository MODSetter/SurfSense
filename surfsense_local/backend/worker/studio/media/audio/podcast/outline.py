from dataclasses import dataclass

from modules.artifacts.podcast.brief import MINUTES, PodcastBrief
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


def prompt(brief: PodcastBrief, focus: str | None) -> str:
    words = target_words(brief)
    segments = max(1, round(words / WORDS_PER_SEGMENT))
    focus_line = (
        f"\nThe listener asked the episode to focus on: {focus}\n" if focus else ""
    )
    return (
        "You are a podcast showrunner planning an episode before any dialogue is "
        f"written. The episode language is {brief.language}. The format is "
        f"{brief.style.value}.\nSpeakers:\n{roster(brief)}\n{focus_line}\n"
        f"Plan an outline that, fully drafted, reaches about {words} words of "
        f"spoken dialogue in about {segments} segments: an opening, distinct topic "
        "areas grounded in the sources, and a closing. Give the episode a short "
        "title. For each segment give a short title, 2-5 concrete talking_points "
        "drawn from the sources, and target_words (the sum should approximate the "
        "total).\n"
        'Return only JSON, no prose: {"title": str, "segments": [{"title": str, '
        '"talking_points": [str], "target_words": int}]}'
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
