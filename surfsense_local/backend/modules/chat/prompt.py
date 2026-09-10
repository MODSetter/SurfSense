import re
from collections import defaultdict
from dataclasses import dataclass

from shared.search import Hit

# Same contract as the cloud chat: the model copies a visible [n], the server
# rewrites it to [citation:<chunk_id>] for the renderer.
INSTRUCTION = (
    "Answer the question using the sources in the context below.\n"
    "Cite with one token: the bracket label [n].\n"
    "- Put the label right after the claim it supports.\n"
    "- Several sources for one claim: stack brackets, [1][2].\n"
    "- Copy labels exactly as shown — never write a title, id, or "
    "[citation:...] yourself.\n"
    "- Only cite claims the sources support. If nothing shown backs a claim, "
    "leave it uncited; never invent one.\n"
    "- If the context does not hold the answer, say so, then answer from your "
    "own knowledge if you can.\n"
    "- Respond in the same language as the question.\n"
    "- Label fenced code blocks with their language, such as python, "
    "typescript, sql, or bash.\n"
    "- Do not repeat the source tags back in your answer.\n"
    'Example: "The method raised efficiency by 20% [1]."'
)

_HEADER = (
    "These are excerpts from the user's knowledge base, selected for this query.\n"
    "A document is a full source; each <document> below is in excerpt view, so "
    "you are seeing only the chunks that matched this query, not the whole "
    "source. Cite a chunk with its [n]."
)

# A chunk that contains these could otherwise close a source early and forge its
# own, so its angle brackets are defanged before it goes between the tags.
_TAGS = re.compile(
    r"</?(?:source|context|document|retrieved_context)\b[^>]*>", re.IGNORECASE
)

# Fenced (```...```) and inline (`...`) code, so citation-shaped examples remain
# literal. Mirrors the frontend Markdown renderer and the cloud normalizer.
_CODE = re.compile(r"```[\s\S]*?```|`[^`\n]+`")
# Citation wrapper first so `[citation:1]` is not eaten as a trailing `[1]`.
_TOKEN = re.compile(r"\[citation:\s*(\d+)\s*\]|\[\s*(\d+)\s*\]")


@dataclass(frozen=True)
class Citation:
    """A source id the model may cite, resolved back to where it came from."""

    source_id: int
    chunk_id: int
    document_id: int
    start_line: int | None
    end_line: int | None
    title: str = ""


def build_context(hits: list[Hit]) -> tuple[str, list[Citation]]:
    """The grounding system message and the citations its ids point at.

    Hits become `[n]`-labelled excerpts grouped by document, matching the cloud
    retrieved_context block. The model cites `[n]`; resolve_citations rewrites
    those to `[citation:<chunk_id>]`. No hits leaves the instruction alone.
    """
    if not hits:
        return INSTRUCTION, []

    citations: list[Citation] = []
    grouped: dict[int, list[tuple[Citation, Hit]]] = defaultdict(list)
    order: list[int] = []
    for i, hit in enumerate(hits, start=1):
        citation = Citation(
            i,
            hit.chunk_id,
            hit.document_id,
            hit.start_line,
            hit.end_line,
            hit.title,
        )
        citations.append(citation)
        if hit.document_id not in grouped:
            order.append(hit.document_id)
        grouped[hit.document_id].append((citation, hit))

    documents = []
    for document_id in order:
        passages = grouped[document_id]
        title = _attr(passages[0][0].title)
        lines = [f'<document title="{title}" view="excerpt">']
        for citation, hit in passages:
            body = _defang(hit.content).strip().replace("\n", "\n" + " " * 6)
            lines.append(f"  [{citation.source_id}] {body}")
        lines.append("</document>")
        documents.append("\n".join(lines))

    context = (
        f"{INSTRUCTION}\n\n<retrieved_context>\n{_HEADER}\n"
        + "\n".join(documents)
        + "\n</retrieved_context>"
    )
    return context, citations


def resolve_citations(
    answer: str, citations: list[Citation]
) -> tuple[str, list[Citation]]:
    """Rewrite model `[n]` labels into `[citation:<chunk_id>]` markers.

    `[citation:n]` is accepted as the same ordinal so a model that still emits
    the old wrapper is not left with a dead chip. Invented numbers are dropped.
    Citation-shaped text inside code remains literal.
    """
    if not answer:
        return answer, []

    by_id = {citation.source_id: citation for citation in citations}
    order: list[int] = []

    def collect(span: str) -> str:
        for match in _TOKEN.finditer(span):
            cited = int(match.group(1) or match.group(2))
            if cited in by_id and cited not in order:
                order.append(cited)
        return span

    _outside_code(answer, collect)

    def rewrite(span: str) -> str:
        def one(match: re.Match[str]) -> str:
            cited = int(match.group(1) or match.group(2))
            return f"[citation:{by_id[cited].chunk_id}]" if cited in by_id else ""

        return _TOKEN.sub(one, span)

    used = [by_id[source_id] for source_id in order]
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


def _attr(value: str) -> str:
    collapsed = " ".join(str(value).split())
    return (
        collapsed.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
