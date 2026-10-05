import re
from collections import defaultdict
from dataclasses import dataclass

from modules.llm import prompting
from modules.llm.profile import Tier
from shared.search import Hit

_HEADER = (
    "These are excerpts from the user's knowledge base, selected for this query.\n"
    "A document is a full source; each <document> below is in excerpt view, so "
    "you are seeing only the chunks that matched this query, not the whole "
    "source. Cite a chunk with its [n]."
)

# Replaces the tier instruction when nothing was retrieved: its citation rules
# cannot apply, and Qwen3 1.7B obeyed them by inventing a [1] in the chat eval.
_NO_SOURCES = (
    "Nothing in the user's knowledge base matched this question, so there are "
    "no sources to work from.\n\n"
    "- Start with one sentence saying the knowledge base does not cover this.\n"
    "- Then, if the answer is general knowledge, give it in the same reply. "
    "Never guess details about the user's own documents, products or people.\n"
    "- Respond in the same language as the question.\n"
    "- Label fenced code blocks with their language, such as python, "
    "typescript, sql, or bash."
)

# A chunk that contains these could otherwise close a source early and forge its
# own, so its angle brackets are defanged before it goes between the tags.
_TAGS = re.compile(
    r"</?(?:source|context|document|retrieved_context)\b[^>]*>", re.IGNORECASE
)

# Fenced (```...```) and inline (`...`) code, so citation-shaped examples remain
# literal. Mirrors the frontend Markdown renderer.
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


@dataclass(frozen=True)
class TurnGrounding:
    """What one turn is answered from.

    The instruction is the system message and the excerpts ride with the
    question: llama-server reuses a prompt only up to its first changed token,
    and what is retrieved changes with every question.
    """

    instruction: str
    # None when nothing matched; the instruction then says so instead.
    excerpts: str | None
    citations: list[Citation]


def build_context(hits: list[Hit], tier: Tier) -> TurnGrounding:
    """The instruction, this turn's excerpts and the citations their ids point at.

    Hits become `[n]`-labelled excerpts grouped by document. The model cites
    `[n]`; resolve_citations rewrites those to `[citation:<chunk_id>]`. No hits
    sends an instruction with nothing to cite, the same for every tier.
    """
    if not hits:
        return TurnGrounding(_NO_SOURCES, None, [])
    # The model copies a visible [n]; the server rewrites it to
    # [citation:<chunk_id>] for the renderer.
    instruction = prompting.load(__package__, tier)

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

    excerpts = (
        f"<retrieved_context>\n{_HEADER}\n"
        + "\n".join(documents)
        + "\n</retrieved_context>"
    )
    return TurnGrounding(instruction, excerpts, citations)


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
