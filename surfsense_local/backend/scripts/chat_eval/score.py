"""What a reply earns against its case, by rules. A judge model is later work."""

import unicodedata
from collections import Counter
from dataclasses import dataclass

from chat_eval.cases import Case
from modules.chat.prompt import Citation, resolve_citations

# resolve_citations reports only the labels it is given, so it gets every label a
# reply could plausibly write. ponytail: a label past 999 goes unseen.
_ANY_LABEL = [Citation(n, n, 0, None, None) for n in range(1000)]


@dataclass(frozen=True)
class Score:
    # Stopped by the 1,024-token cap, which reasoning tokens spend too.
    truncated: bool
    empty: bool
    # Labels naming no passage. Chat drops them, so the claim loses its source.
    invented: int
    # Every supporting passage cited; None when no passage holds the answer.
    cites_support: bool | None
    # A passage cited that does not hold the answer.
    cites_other: bool
    # Every expected fact present; None when the case expects none.
    facts: bool | None
    # Written in the question's script, which stands in for its language.
    same_script: bool


def score(case: Case, answer: str, finish_reason: str | None) -> Score:
    labels = _labels(answer)
    cited = {n for n in labels if 1 <= n <= len(case.passages)}
    supporting = set(case.supporting)
    folded = answer.casefold()
    return Score(
        truncated=finish_reason == "length",
        empty=not answer.strip(),
        invented=len(labels) - len(cited),
        cites_support=supporting <= cited if supporting else None,
        cites_other=bool(cited - supporting),
        facts=all(f.casefold() in folded for f in case.facts) if case.facts else None,
        same_script=_script(answer) == _script(case.question),
    )


def _labels(answer: str) -> list[int]:
    """Each distinct [n] the reply wrote, read exactly as chat reads them."""
    _, used = resolve_citations(answer, _ANY_LABEL)
    return [citation.source_id for citation in used]


def _script(text: str) -> str | None:
    """The script most of the letters are in, as Unicode names it: LATIN, CJK...

    ponytail: a script, not a language, so French answered in English passes.
    A judge model or a language detector is the upgrade.
    """
    scripts = Counter(
        unicodedata.name(char, "").split(" ")[0] for char in text if char.isalpha()
    )
    return scripts.most_common(1)[0][0] if scripts else None
