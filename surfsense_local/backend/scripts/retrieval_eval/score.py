"""Where the answer landed in a ranking, which is all retrieval can be judged on."""

from dataclasses import dataclass

from retrieval_eval.cases import Query

# What chat puts in the prompt (`retrieve(..., top_k=5)`), so a hit below this
# was found by retrieval and still never reached the model.
PROMPT_PASSAGES = 5


@dataclass(frozen=True)
class Ranking:
    found: bool
    # 1-based position of the first passage that answers the query.
    rank: int | None
    in_top_5: bool


def score(query: Query, passages: list[str]) -> Ranking:
    for position, passage in enumerate(passages, start=1):
        if _answers(query, passage):
            return Ranking(True, position, position <= PROMPT_PASSAGES)
    return Ranking(False, None, False)


def _answers(query: Query, passage: str) -> bool:
    """Chunking may fold whitespace, so compare on collapsed text."""
    folded = " ".join(passage.split()).casefold()
    return any(" ".join(phrase.split()).casefold() in folded for phrase in query.expect)
