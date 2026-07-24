"""MMLongBench-Doc prompt template.

Both arms get the same prompt — only the document delivery channel
differs (native PDF embedded in the OpenRouter request vs SurfSense
RAG retrieval). The format hint in the prompt mirrors what the
upstream paper uses so the grader's regex can reliably extract the
answer.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Per-format hint blocks
# ---------------------------------------------------------------------------

_FORMAT_HINTS: dict[str, str] = {
    "str": (
        "Respond with the answer as a short phrase, no full sentence. "
        "Format your final line as `Answer: <text>`."
    ),
    "int": ("Respond with a single integer only. Format your final line as `Answer: <integer>`."),
    "float": (
        "Respond with a single decimal number only (no units). "
        "Format your final line as `Answer: <number>`."
    ),
    "list": (
        "Respond with a comma-separated list of items, no extra text. "
        "Format your final line as `Answer: item1, item2, item3`."
    ),
    "none": (
        "If the answer cannot be determined from the document, say so explicitly. "
        "Format your final line as `Answer: Not answerable`."
    ),
}


_PROMPT = """\
You are a document-understanding assistant. Use ONLY the provided
document to answer the question. The document may contain text,
tables, charts, figures, and images. If the answer is in a chart or
image, read it carefully. Do not use external knowledge.

Question: {question}

{format_hint}
"""


def build_prompt(question: str, *, answer_format: str) -> str:
    """Assemble the full prompt for one MMLongBench question."""

    fmt = (answer_format or "str").strip().lower()
    hint = _FORMAT_HINTS.get(fmt, _FORMAT_HINTS["str"])
    return _PROMPT.format(question=question.strip(), format_hint=hint)


__all__ = ["build_prompt"]
