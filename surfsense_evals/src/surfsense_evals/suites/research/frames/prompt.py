"""FRAMES prompt templates.

Two templates: one for the bare-LLM arm (no retrieval), one for
SurfSense (the agent retrieves; we mostly just instruct it on
output format). Both arms must use byte-identical *content* for the
question itself so the head-to-head is fair — the wrappers diverge
only in framing.

Format expectations (mirrors the FRAMES paper, section 4):

* Short factual answer — names, dates, numbers, ordinals
* No extra explanation in the final line; we anchor on
  ``Answer: <text>`` for deterministic extraction
* Free-text reasoning is *allowed* before the final ``Answer:`` line —
  multi-hop questions often benefit from it. We just don't grade it.
"""

from __future__ import annotations

_BASE_INSTRUCTIONS = (
    "You are a careful question-answering assistant. The question may "
    "require combining facts from multiple sources, doing arithmetic, "
    "or reasoning about dates. Think step by step if needed, then give "
    "the final answer.\n\n"
    "Format your final line EXACTLY as:\n"
    "Answer: <short answer>\n\n"
    "The answer should be as short as possible — a name, a number, a "
    "date, a single phrase. Do not repeat the question. Do not include "
    "punctuation at the end unless it is part of the answer."
)


_BARE_TEMPLATE = """\
{instructions}

Question: {question}
"""


_SURFSENSE_TEMPLATE = """\
{instructions}

You have access to a Wikipedia knowledge base via retrieval. Use it
to look up any facts you are not confident about. The corpus contains
the Wikipedia articles needed to answer this question, but you must
retrieve them yourself — they are not pre-selected.

Question: {question}
"""


def build_bare_prompt(question: str) -> str:
    """Prompt for the no-retrieval baseline arm."""

    return _BARE_TEMPLATE.format(
        instructions=_BASE_INSTRUCTIONS,
        question=question.strip(),
    )


def build_surfsense_prompt(question: str) -> str:
    """Prompt for the SurfSense arm (retrieval-augmented)."""

    return _SURFSENSE_TEMPLATE.format(
        instructions=_BASE_INSTRUCTIONS,
        question=question.strip(),
    )


__all__ = ["build_bare_prompt", "build_surfsense_prompt"]
