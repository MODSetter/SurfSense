"""Which passages a question is shown: all of them when they fit, else its best few, found by
the document's title as well as by the passage's own words."""

import pytest

from modules.jobs.evidence.passages import SourceText, passages_of
from modules.jobs.evidence.retrieval import Retriever
from modules.jobs.workbook_rows.ask import passages_block

pytestmark = pytest.mark.unit

FILLER = "\n\n".join(
    f"## Note {n}\n\nRoutine text about meetings number {n}." for n in range(40)
)
SOURCES = [
    SourceText(
        1,
        "access-management-policy",
        "## Policy\n\nRequests are approved before any change.",
    ),
    SourceText(2, "meeting-notes", FILLER),
]


def test_every_passage_is_shown_when_they_fit():
    """Within the budget nothing is left out, in the order the sources wrote it."""
    passages = passages_of(SOURCES)
    retriever = Retriever(passages, budget_chars=1_000_000, per_question=2)

    assert retriever.whole
    assert retriever.for_question("anything") == list(range(len(passages)))


def test_passages_whose_texts_fit_but_not_as_the_prompt_shows_them_are_not_whole():
    """The prompt shows each passage under its document's title, its heading and its lines:
    a budget the texts alone fit, but not as shown, gives each question its best few."""
    source = SourceText(
        1,
        "information-security-policy-and-acceptable-use-standard",
        "\n\n".join(
            f"## Control {n}: access reviews\n\nAccess is reviewed." for n in range(20)
        ),
    )
    passages = passages_of([source])
    shown = len(passages_block(passages, list(range(len(passages)))))

    assert sum(len(p.text) for p in passages) < shown - 1
    assert not Retriever(passages, budget_chars=shown - 1, per_question=2).whole


def test_a_passage_is_found_by_its_documents_title():
    """A policy's own name counts: "access management" finds the access management policy's passage."""
    passages = passages_of(SOURCES)
    retriever = Retriever(passages, budget_chars=100, per_question=2)

    shown = retriever.for_question("Are access management policies established?")

    assert not retriever.whole
    assert passages[shown[0]].title == "access-management-policy"


def test_a_standing_query_shows_its_passages_with_every_question():
    """How the firm reviews its policies reaches a question that never says "review"."""
    sources = [
        *SOURCES,
        SourceText(
            3, "policy-management", "## Review\n\nPolicies are reviewed yearly."
        ),
    ]
    passages = passages_of(sources)
    retriever = Retriever(
        passages,
        budget_chars=100,
        per_question=1,
        standing=("policies reviewed yearly",),
        per_standing=1,
    )

    shown = [passages[i].title for i in retriever.for_question("Is access approved?")]

    assert shown == ["access-management-policy", "policy-management"]


def test_with_an_embedder_meaning_takes_turns_with_the_words():
    """A passage no word of the question names is shown when the embedder finds it close."""
    sources = [
        *SOURCES,
        SourceText(3, "vendors", "## Vendors\n\nSuppliers are vetted."),
    ]
    passages = passages_of(sources)
    vendors = next(i for i, p in enumerate(passages) if p.title == "vendors")

    def embed(texts, query):
        # The question and the vendors passage point one way, everything else another.
        return [
            [1.0, 0.0] if query or "Suppliers" in text else [0.0, 1.0] for text in texts
        ]

    words_only = Retriever(passages, budget_chars=100, per_question=2)
    with_meaning = Retriever(passages, budget_chars=100, per_question=2, embed=embed)
    question = "Is supply chain risk managed for the access management policy?"
    policy = next(i for i, p in enumerate(passages) if p.title.startswith("access"))

    assert vendors not in words_only.for_question(question)
    # The two rankings take turns: words' best, then meaning's best.
    assert with_meaning.for_question(question) == sorted([policy, vendors])


def test_a_standing_query_with_no_strong_match_pins_nothing():
    """A query no passage answers well shows nothing with every question rather than noise."""
    passages = passages_of(SOURCES)
    retriever = Retriever(
        passages,
        budget_chars=100,
        per_question=1,
        standing=("how often the firm's insurance cover is renewed",),
    )

    assert retriever.pinned == []


def test_passages_are_embedded_in_batches():
    """The embedder is asked a batch at a time, so a cancel can come between batches."""
    from modules.jobs.evidence.retrieval import EMBED_BATCH

    filler = "\n\n".join(f"## Part {n}\n\nText {n}." for n in range(EMBED_BATCH + 5))
    passages = passages_of([SourceText(1, "long", filler)])
    sizes: list[int] = []

    def embed(texts, query):
        if not query:
            sizes.append(len(texts))
        return [[1.0, 0.0] for _ in texts]

    Retriever(passages, budget_chars=100, per_question=2, embed=embed)

    assert sizes == [EMBED_BATCH, len(passages) - EMBED_BATCH]


def test_passage_vectors_are_embedded_once_per_embedder_and_text():
    """A second run over the same library embeds nothing new; a changed passage, another
    embedder, and every query are embedded afresh."""
    from modules.jobs.evidence import vectors

    calls: list[tuple[tuple[str, ...], bool]] = []

    def embed(texts: list[str], query: bool) -> list[list[float]]:
        calls.append((tuple(texts), query))
        return [[float(len(text)), 1.0] for text in texts]

    vectors.forget()
    first = vectors.remembered(embed, "bge@1")
    assert first(["a policy", "a standard"], False) == [[8.0, 1.0], [10.0, 1.0]]
    again = vectors.remembered(embed, "bge@1")
    assert again(["a standard", "a new policy"], False) == [[10.0, 1.0], [12.0, 1.0]]
    vectors.remembered(embed, "other@2")(["a policy"], False)
    again(["a policy"], True)
    again(["a policy"], True)

    assert calls == [
        (("a policy", "a standard"), False),
        (("a new policy",), False),
        (("a policy",), False),
        (("a policy",), True),
        (("a policy",), True),
    ]
    vectors.forget()
