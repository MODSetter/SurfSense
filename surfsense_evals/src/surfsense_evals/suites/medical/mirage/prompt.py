"""MedRAG ``{step_by_step_thinking, answer_choice}`` MCQ prompt.

Mirrors the MedRAG paper's prompt format so accuracy numbers are
comparable to the published MIRAGE leaderboard.
"""

from __future__ import annotations

from collections.abc import Mapping

_PROMPT_TEMPLATE = """\
You are a helpful medical expert. Answer the following multiple-choice
question using the relevant medical knowledge available to you (and any
retrieved context, if provided).

Respond with a JSON object on a single line:
{{"step_by_step_thinking": "<your reasoning>", "answer_choice": "<letter>"}}

Question: {question}

Options:
{options_block}
"""


def _options_block(options: Mapping[str, str]) -> str:
    parts: list[str] = []
    for letter in sorted(options.keys()):
        text = options.get(letter)
        if text is None or text == "":
            continue
        parts.append(f"{letter}) {text}")
    return "\n".join(parts)


def build_prompt(question: str, options: Mapping[str, str]) -> str:
    return _PROMPT_TEMPLATE.format(
        question=question.strip(),
        options_block=_options_block(options),
    )


__all__ = ["build_prompt"]
