"""Prompt templates for the three input modalities in parser_compare.

We deliberately reuse the *same* core question framing as
``mmlongbench/prompt.py`` so byte-identical questions reach all six
arms; only the document delivery channel changes.

Three templates:

* ``build_native_pdf_prompt``       — bare question + format hint.
                                       The PDF rides as a separate file
                                       part (``NativePdfArm`` handles it).
* ``build_long_context_prompt``     — question + format hint + the
                                       parser-extracted markdown wrapped
                                       in fenced ``<document>`` tags so
                                       the model can clearly delimit
                                       "context" from "instruction".
* ``build_surfsense_prompt``        — bare question + format hint
                                       (chunks come from RAG retrieval,
                                       not from the prompt).

The ``<document>`` tag is doc-aware: even though parser_compare runs
one PDF per question today, we keep the wrapper plural so this is
trivial to extend to multi-doc later.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Per-format hint blocks (same lookup as mmlongbench/prompt.py)
# ---------------------------------------------------------------------------

_FORMAT_HINTS: dict[str, str] = {
    "str": (
        "Respond with the answer as a short phrase, no full sentence. "
        "Format your final line as `Answer: <text>`."
    ),
    "int": (
        "Respond with a single integer only. "
        "Format your final line as `Answer: <integer>`."
    ),
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


def _format_hint(answer_format: str) -> str:
    fmt = (answer_format or "str").strip().lower()
    return _FORMAT_HINTS.get(fmt, _FORMAT_HINTS["str"])


_BASE_INSTRUCTION = (
    "You are a document-understanding assistant. Use ONLY the provided "
    "document to answer the question. The document may contain text, "
    "tables, charts, figures, and images. If the answer is in a chart "
    "or image, read it carefully. Do not use external knowledge."
)


def build_native_pdf_prompt(question: str, *, answer_format: str) -> str:
    """Prompt for ``NativePdfArm`` — PDF attached separately as a file part."""

    return (
        f"{_BASE_INSTRUCTION}\n\n"
        f"Question: {question.strip()}\n\n"
        f"{_format_hint(answer_format)}\n"
    )


def build_surfsense_prompt(question: str, *, answer_format: str) -> str:
    """Prompt for ``SurfSenseArm`` — chunks retrieved by the agent."""

    # SurfSense's agent already injects retrieved chunks via its tool
    # loop; the prompt only carries the user-visible question + format
    # hint, mirroring how a human asks the SurfSense UI.
    return (
        f"{_BASE_INSTRUCTION}\n\n"
        f"Question: {question.strip()}\n\n"
        f"{_format_hint(answer_format)}\n"
    )


def build_long_context_prompt(
    question: str,
    *,
    answer_format: str,
    document_markdown: str,
    document_label: str,
) -> str:
    """Prompt for the four long-context arms — markdown stuffed inline.

    ``document_label`` is a short human-readable name (e.g. the PDF
    filename) so the model can reason about source provenance even
    though only one document is in scope.
    """

    return (
        f"{_BASE_INSTRUCTION}\n\n"
        f"<document name=\"{document_label}\">\n"
        f"{document_markdown.strip()}\n"
        f"</document>\n\n"
        f"Question: {question.strip()}\n\n"
        f"{_format_hint(answer_format)}\n"
    )


__all__ = [
    "build_long_context_prompt",
    "build_native_pdf_prompt",
    "build_surfsense_prompt",
]
