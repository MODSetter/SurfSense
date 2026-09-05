import re
from dataclasses import dataclass

from shared.search import Hit

# Precedes the retrieved context. Kept a constant, not a setting, for v1. The
# explicit rules and example matter most for the small local models this targets.
INSTRUCTION = (
    "Answer the question using the sources in the context below.\n"
    "- Cite each claim inline with the source's id in square brackets, like [1], "
    "and only cite a source that carries an id.\n"
    "- If the context does not hold the answer, say so, then answer from your own "
    "knowledge if you can.\n"
    "- Respond in the same language as the question.\n"
    "- Do not repeat the source tags back in your answer.\n"
    'Example: "The method raised efficiency by 20% [1]."'
)

# A chunk that contains these could otherwise close a source early and forge its
# own, so its angle brackets are defanged before it goes between the tags.
_TAGS = re.compile(r"</?(?:source|context)\b[^>]*>", re.IGNORECASE)


@dataclass(frozen=True)
class Citation:
    """A source id the model may cite, resolved back to where it came from."""

    id: int
    chunk_id: int
    document_id: int
    start_line: int | None
    end_line: int | None


def build_context(hits: list[Hit]) -> tuple[str, list[Citation]]:
    """The grounding system message and the citations its ids point at.

    Hits become `<source id="N">` blocks in rank order; the model cites `[N]` and
    the frontend resolves each id through the returned citations. No hits leaves
    the instruction alone, and the model is told to fall back to its own knowledge.
    """
    if not hits:
        return INSTRUCTION, []

    citations = [
        Citation(i, hit.chunk_id, hit.document_id, hit.start_line, hit.end_line)
        for i, hit in enumerate(hits, start=1)
    ]
    sources = "\n".join(
        f'<source id="{citation.id}" document="{citation.document_id}"'
        f' lines="{_lines(citation)}">{_defang(hit.content)}</source>'
        for citation, hit in zip(citations, hits, strict=True)
    )
    return f"{INSTRUCTION}\n\n<context>\n{sources}\n</context>", citations


def _defang(content: str) -> str:
    """Strip any source or context tags a chunk carries, so it can't break out."""
    return _TAGS.sub("", content)


def _lines(citation: Citation) -> str:
    if citation.start_line is None or citation.end_line is None:
        return ""
    return f"{citation.start_line}-{citation.end_line}"
