"""MedXpertQA-MM prompt.

Mirrors the upstream paper's evaluation prompt (Zuo et al., ICML 2025
§3.4): present case + 5 options A-E, ask for a single letter answer.
We also instruct the model to use the embedded images explicitly,
since the whole point of the MM subset is that the answer depends on
visual evidence (radiology / dermoscopy / pathology / ECG, etc.).
"""

from __future__ import annotations

from collections.abc import Mapping

ANSWER_LETTERS = ("A", "B", "C", "D", "E")


_PROMPT = """\
You are a board-certified physician. The following exam question
includes a clinical case and one or more medical images (radiology,
dermatology, pathology, ECG, etc.). Use BOTH the text and the images
to choose the best answer. Do not rely on memorisation of the case;
read the images carefully — they often determine the correct answer.

Case + question:
{question}

Answer choices:
{options_block}

Respond on a single line in the format `Answer: X` where X is one of
A, B, C, D, or E.
"""


def format_options(options: Mapping[str, str]) -> str:
    """Render the ``A) ... E) ...`` options block."""

    parts: list[str] = []
    for letter in ANSWER_LETTERS:
        text = options.get(letter)
        if text is None or str(text).strip() == "":
            continue
        parts.append(f"{letter}) {str(text).strip()}")
    return "\n".join(parts)


def build_prompt(question: str, options: Mapping[str, str]) -> str:
    return _PROMPT.format(
        question=question.strip(),
        options_block=format_options(options),
    )


__all__ = ["ANSWER_LETTERS", "build_prompt", "format_options"]
