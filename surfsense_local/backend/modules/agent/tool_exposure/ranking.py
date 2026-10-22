"""Ready plugin tools in the order a request needs them: by keyword and by meaning.

Each leg ranks every tool and reciprocal rank fusion merges the two, which ranked
tools better than the weighting source search blends its legs with. A tool's
text is its name, description and parameters, and its plugin's line: what every
plugin has, so none ranks ahead for words only some carry.
"""

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from modules.plugins.gateway.ready_tool import ReadyTool
from shared.tokenizer import terms


class Embed(Protocol):
    """A request and tools as vectors; an asymmetric model embeds each its own way."""

    def query(self, text: str) -> list[float]: ...

    def documents(self, texts: list[str]) -> list[list[float]]: ...


# Reciprocal rank fusion's damping: a tool's place counts, not how far ahead it is.
_FUSION_K = 60
# BM25's usual constants.
_K1 = 1.2
_B = 0.75


@dataclass(frozen=True)
class IndexedTool:
    """A ready tool and the line its plugin goes by."""

    ready: ReadyTool
    plugin_line: str = ""

    @property
    def text(self) -> str:
        parameters = " ".join((self.ready.input_schema.get("properties") or {}).keys())
        return "\n".join(
            part
            for part in (
                self.ready.tool.replace("_", " ").replace("-", " "),
                self.ready.title or "",
                self.ready.description,
                parameters,
                self.plugin_line,
            )
            if part
        )


def ranked(
    tools: Sequence[IndexedTool], query: str, embed: Embed | None
) -> list[IndexedTool]:
    """Every tool, best first; with no query, in the order given."""
    if not query.strip():
        return list(tools)
    legs = [_keyword_order(tools, query)]
    if embed is not None:
        legs.append(_meaning_order(tools, query, embed))
    fused: dict[int, float] = {}
    for order in legs:
        for place, index in enumerate(order):
            fused[index] = fused.get(index, 0.0) + 1 / (_FUSION_K + place + 1)
    best = sorted(range(len(tools)), key=lambda i: (-fused.get(i, 0.0), i))
    return [tools[i] for i in best]


def _keyword_order(tools: Sequence[IndexedTool], query: str) -> list[int]:
    """BM25 over each tool's distinct terms, as FTS5 cuts them; ties keep the given order."""
    wanted = set(terms(query))
    documents = [Counter(terms(tool.text)) for tool in tools]
    lengths = [sum(d.values()) for d in documents]
    average = sum(lengths) / len(lengths) if lengths else 0.0
    holding = Counter(term for d in documents for term in d if term in wanted)
    total = len(documents)

    def score(i: int) -> float:
        found = 0.0
        for term in wanted:
            count = documents[i][term]
            if not count:
                continue
            rarity = math.log(1 + (total - holding[term] + 0.5) / (holding[term] + 0.5))
            norm = _K1 * (1 - _B + _B * lengths[i] / (average or 1))
            found += rarity * count * (_K1 + 1) / (count + norm)
        return found

    scores = [score(i) for i in range(total)]
    return [i for i in sorted(range(total), key=lambda i: (-scores[i], i)) if scores[i]]


def _meaning_order(tools: Sequence[IndexedTool], query: str, embed: Embed) -> list[int]:
    asked = embed.query(query)
    near = [_cosine(asked, v) for v in embed.documents([t.text for t in tools])]
    return sorted(range(len(tools)), key=lambda i: (-near[i], i))


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    size = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / size if size else 0.0
