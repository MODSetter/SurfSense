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

# Fenced (```...```) and inline (`...`) code, so an ordinal inside an example or
# `arr[1]` is never mistaken for a citation. Mirrors the frontend markdown.
_CODE = re.compile(r"```[\s\S]*?```|`[^`\n]+`")
_ORDINAL = re.compile(r"\[\s*(\d+)\s*\]")


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


def normalize_citations(
    answer: str, citations: list[Citation]
) -> tuple[str, list[Citation]]:
    """Resolve the answer's inline `[n]` against the sources it was given.

    An `[n]` that names a real source survives; one the model invented is dropped
    rather than left pointing nowhere. The survivors are renumbered densely in
    order of first appearance, so `[1]`, `[2]`, ... match the citations the UI
    lists positionally. Ordinals inside code spans are left untouched.
    """
    if not answer:
        return answer, []

    by_id = {citation.id: citation for citation in citations}

    order: list[int] = []

    def collect(span: str) -> str:
        for match in _ORDINAL.finditer(span):
            cited = int(match.group(1))
            if cited in by_id and cited not in order:
                order.append(cited)
        return span

    _outside_code(answer, collect)
    renumbered = {old: new for new, old in enumerate(order, start=1)}

    def rewrite(span: str) -> str:
        def one(match: re.Match[str]) -> str:
            new = renumbered.get(int(match.group(1)))
            return f"[{new}]" if new is not None else ""

        return _ORDINAL.sub(one, span)

    used = [
        Citation(
            renumbered[old],
            by_id[old].chunk_id,
            by_id[old].document_id,
            by_id[old].start_line,
            by_id[old].end_line,
        )
        for old in order
    ]
    return _outside_code(answer, rewrite), used


def _outside_code(text: str, transform) -> str:
    """Apply `transform` to the non-code spans; code regions pass through as-is."""
    parts: list[str] = []
    last = 0
    for region in _CODE.finditer(text):
        parts.append(transform(text[last : region.start()]))
        parts.append(region.group(0))
        last = region.end()
    parts.append(transform(text[last:]))
    return "".join(parts)


def _defang(content: str) -> str:
    """Strip any source or context tags a chunk carries, so it can't break out."""
    return _TAGS.sub("", content)


def _lines(citation: Citation) -> str:
    if citation.start_line is None or citation.end_line is None:
        return ""
    return f"{citation.start_line}-{citation.end_line}"
