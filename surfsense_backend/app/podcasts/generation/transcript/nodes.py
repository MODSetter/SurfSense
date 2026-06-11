"""Transcript-drafting nodes: plan an outline, draft each beat, then assemble.

Long-form is produced beat-by-beat: a single call plans the structure, then each
segment is drafted on its own with a recap of what came before so the script
stays coherent without holding the whole episode in one context window.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.podcasts.schemas import PodcastSpec, Transcript, TranscriptTurn
from app.services.llm_service import get_agent_llm

from ..prompts import draft_segment_prompt, plan_outline_prompt
from ..structured import invoke_json
from .config import TranscriptConfig
from .planning import Outline, OutlineSegment, SegmentDraft
from .state import TranscriptState

# Average speaking rate; converts target minutes to a target word count.
_WORDS_PER_MINUTE = 150
# Rough words per outline segment, used to suggest how many segments to plan.
_WORDS_PER_SEGMENT = 250
# Cap on source text sent per LLM call to bound tokens on large sources.
_SOURCE_BUDGET_CHARS = 12000
# How much prior dialogue to recap into each segment for continuity.
_RECAP_CHARS = 800


async def plan_outline(
    state: TranscriptState, config: RunnableConfig
) -> dict[str, Any]:
    """Plan the segment structure sized to the spec's target duration."""
    tc = TranscriptConfig.from_runnable_config(config)
    llm = await _require_llm(state, tc)

    target_words = round(tc.spec.duration.midpoint_minutes * _WORDS_PER_MINUTE)
    suggested_segments = max(1, round(target_words / _WORDS_PER_SEGMENT))

    messages = [
        SystemMessage(
            content=plan_outline_prompt(
                spec=tc.spec,
                target_words=target_words,
                suggested_segments=suggested_segments,
                focus=tc.focus,
            )
        ),
        HumanMessage(content=_source_block(state.source_content)),
    ]
    outline = await invoke_json(llm, messages, Outline)
    return {"outline": outline}


async def draft_segments(
    state: TranscriptState, config: RunnableConfig
) -> dict[str, Any]:
    """Draft each outline segment in order, carrying a running recap."""
    tc = TranscriptConfig.from_runnable_config(config)
    llm = await _require_llm(state, tc)
    outline = state.outline
    if outline is None:
        raise RuntimeError("draft_segments requires an outline")

    source_block = _source_block(state.source_content)
    turns: list[TranscriptTurn] = []
    total = len(outline.segments)

    for index, segment in enumerate(outline.segments):
        messages = [
            SystemMessage(
                content=draft_segment_prompt(
                    spec=tc.spec,
                    segment=segment,
                    position=index + 1,
                    total=total,
                    recap=_recap(turns, tc.spec),
                )
            ),
            HumanMessage(content=source_block),
        ]
        draft = await invoke_json(llm, messages, SegmentDraft)
        turns.extend(_valid_turns(draft, tc.spec))

    return {"drafted_turns": turns}


def finalize(state: TranscriptState, config: RunnableConfig) -> dict[str, Any]:
    """Assemble drafted turns into a validated transcript."""
    if not state.drafted_turns:
        raise RuntimeError("drafting produced no usable dialogue")
    return {"transcript": Transcript(turns=state.drafted_turns)}


async def _require_llm(state: TranscriptState, tc: TranscriptConfig):
    llm = await get_agent_llm(state.db_session, tc.search_space_id)
    if llm is None:
        raise RuntimeError(
            f"no agent LLM configured for search space {tc.search_space_id}"
        )
    return llm


def _source_block(source_content: str) -> str:
    sample = (source_content or "")[:_SOURCE_BUDGET_CHARS]
    return f"<source_content>{sample}</source_content>"


def _valid_turns(draft: SegmentDraft, spec: PodcastSpec) -> list[TranscriptTurn]:
    # Drop any turn the model attributed to a slot the spec doesn't define, so a
    # stray attribution can't break rendering downstream.
    valid_slots = {speaker.slot for speaker in spec.speakers}
    return [turn for turn in draft.turns if turn.speaker in valid_slots]


def _recap(turns: list[TranscriptTurn], spec: PodcastSpec) -> str | None:
    if not turns:
        return None
    names = {speaker.slot: speaker.name for speaker in spec.speakers}
    rendered = "\n".join(
        f"{names.get(turn.speaker, turn.speaker)}: {turn.text}" for turn in turns
    )
    return rendered[-_RECAP_CHARS:]
