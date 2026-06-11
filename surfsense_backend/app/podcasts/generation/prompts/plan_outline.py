"""Prompt for planning a long-form podcast outline before drafting dialogue.

Outlining first is what makes long-form reliable: a single LLM call cannot hold
a coherent one- to two-hour script, but it can plan segments that are then
drafted independently against a shared plan. The prompt is told the target
length so the number and size of segments scale with the requested duration.
"""

from __future__ import annotations

from app.podcasts.schemas import PodcastSpec

from .speakers import render_speaker_roster


def plan_outline_prompt(
    *,
    spec: PodcastSpec,
    target_words: int,
    suggested_segments: int,
    focus: str | None,
) -> str:
    focus_block = (
        f"\nThe user asked the episode to focus on:\n{focus}\n" if focus else ""
    )
    return f"""\
You are a podcast showrunner planning the structure of an episode before any \
dialogue is written.

The episode language is {spec.language}. The format is {spec.style.value}.
Speakers (refer to them by these slots later):
{render_speaker_roster(spec)}
{focus_block}
Plan an outline that, when fully drafted, reaches roughly {target_words} words \
of spoken dialogue (about {suggested_segments} segments). Each segment is one \
coherent beat of the conversation: an opening, distinct topic areas grounded in \
the source content, and a closing.

For each segment provide:
- title: a short label for the beat
- talking_points: 2-5 concrete points to cover, drawn from the source content
- target_words: how many words of dialogue this segment should run (the sum \
across segments should approximate {target_words})

Respond with strict JSON and nothing else:
{{"segments": [{{"title": "...", "talking_points": ["..."], "target_words": 0}}]}}
"""
