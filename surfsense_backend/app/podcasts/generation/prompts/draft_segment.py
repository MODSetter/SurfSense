"""Prompt for drafting one outline segment into dialogue turns.

Each segment is drafted on its own so long episodes stay coherent and within
context limits. A short recap of the preceding dialogue is passed in so the new
segment continues naturally instead of restarting. The model must write in the
episode language and attribute every line to a real speaker slot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.podcasts.schemas import PodcastSpec

from .speakers import render_speaker_roster

if TYPE_CHECKING:
    from app.podcasts.generation.transcript.planning import OutlineSegment


def draft_segment_prompt(
    *,
    spec: PodcastSpec,
    segment: OutlineSegment,
    position: int,
    total: int,
    recap: str | None,
) -> str:
    talking_points = "\n".join(f"- {point}" for point in segment.talking_points)
    recap_block = (
        f"\nRecap of the conversation so far (continue from here, do not repeat "
        f"it):\n{recap}\n"
        if recap
        else "\nThis is the opening segment; begin the conversation naturally.\n"
    )
    return f"""\
You are scripting natural, engaging podcast dialogue for segment {position} of \
{total}.

Write entirely in {spec.language}. The format is {spec.style.value}.
Speakers — attribute every line using these exact slot numbers:
{render_speaker_roster(spec)}
{recap_block}
This segment is "{segment.title}". Cover these points using only facts grounded \
in the provided source content:
{talking_points}

Aim for about {segment.target_words} words of dialogue. Keep turns conversational \
and varied; speakers should react to each other rather than deliver monologues. \
Do not add greetings or sign-offs unless this is the first or last segment.

Respond with strict JSON and nothing else:
{{"turns": [{{"speaker": <slot>, "text": "..."}}]}}
"""
