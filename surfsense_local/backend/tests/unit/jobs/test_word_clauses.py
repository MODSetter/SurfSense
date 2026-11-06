"""The word-clauses runner reviews a contract against the firm's playbook: every change is a tracked
change whose playbook quote and contract text were found, anything it cannot settle goes to a person,
and its operations always apply."""

import json
from pathlib import Path

import docx
import pytest

from modules.artifacts.revised_copies.engines import word
from modules.jobs.asking.model import ModelReply
from modules.jobs.asking.stopped import FillStoppedError
from modules.jobs.evidence.passages import SourceText
from modules.jobs.word_clauses.config import load_config
from modules.jobs.word_clauses.review import NoClausesError, review_contract
from tests.live.revised_files import RedlinedWord

pytestmark = pytest.mark.unit

CLAUSES = [
    "“Confidential Information” means information disclosed in writing and "
    "marked as confidential.",
    "The Receiving Party shall use Confidential Information only to evaluate the Purpose.",
    "The Receiving Party may disclose Confidential Information when required by law.",
    "This Agreement ends two years after the Effective Date.",
]

PLAYBOOK = SourceText(
    3,
    "NDA playbook",
    "## Compelled disclosure\n\nBefore any disclosure the law compels, the Receiving Party "
    "gives the Disclosing Party prompt written notice where the law allows.\n\n"
    "## Oral information\n\nInformation disclosed orally is Confidential Information when "
    "it is identified as confidential at the time of disclosure.\n\n"
    "## Use\n\nThe Receiving Party uses Confidential Information only for the Purpose.",
)

NOTICE = "gives the Disclosing Party prompt written notice where the law allows"
ORAL = "Information disclosed orally is Confidential Information when it is identified as confidential"
USE = "uses Confidential Information only for the Purpose"


def write_config(tmp_path: Path, check: bool = False) -> Path:
    """The runner's settings as a pack brings them, with stand-in prompts."""
    folder = tmp_path / "job"
    (folder / "prompts").mkdir(parents=True)
    prompts = {
        "system.md": "Review one point. Verdicts: $verdicts.",
        "point.md": "$outline\n\n$passages\n\nPoint: $point ($covers)",
        "repair.md": "$problem",
        "check.md": "Does the playbook support this change for $point?",
    }
    for name, text in prompts.items():
        (folder / "prompts" / name).write_text(text, encoding="utf-8")
    raw = {
        "points": [
            {
                "key": "use",
                "title": "Limited use",
                "covers": "What the Receiving Party may use Confidential Information for.",
                "queries": ["use of Confidential Information"],
            },
            {
                "key": "compelled-disclosure",
                "title": "Compelled disclosure",
                "covers": "Notice before a disclosure the law compels.",
                "queries": ["compelled disclosure notice"],
            },
            {
                "key": "oral",
                "title": "Oral information",
                "covers": "Whether information disclosed orally is confidential.",
                "queries": ["oral disclosure"],
            },
            {
                "key": "term",
                "title": "Term",
                "covers": "How long the obligations last.",
                "queries": ["term of the agreement"],
            },
        ],
        "prompts": {
            "system": "prompts/system.md",
            "point": "prompts/point.md",
            "repair": "prompts/repair.md",
            **({"check": "prompts/check.md"} if check else {}),
        },
        "settings": [
            {
                "key": "external_comments",
                "label": "Explain each change to the other side",
                "default": True,
            }
        ],
    }
    (folder / "job.json").write_text(json.dumps(raw), encoding="utf-8")
    return folder / "job.json"


@pytest.fixture
def config(tmp_path: Path):
    """The pack's config, without a second check."""
    return load_config(write_config(tmp_path))


def write_contract(tmp_path: Path, clauses: list[str] = CLAUSES) -> Path:
    """A counterparty's NDA: a title and numbered clauses."""
    document = docx.Document()
    document.add_paragraph("MUTUAL NON-DISCLOSURE AGREEMENT", style="Title")
    for text in clauses:
        document.add_paragraph(text, style="List Number")
    path = tmp_path / "NDA.docx"
    document.save(path)
    return path


@pytest.fixture
def contract(tmp_path: Path) -> Path:
    """The NDA every test reviews unless it builds its own."""
    return write_contract(tmp_path)


def verdict(
    said,
    *,
    paragraphs=(),
    quote="",
    kind="none",
    paragraph="",
    old="",
    new="",
    external="",
    internal="Checked against the playbook.",
):
    """A model's reply on one review point."""
    return {
        "paragraphs": list(paragraphs),
        "playbook_passage": 1,
        "playbook_quote": quote,
        "internal_comment": internal,
        "verdict": said,
        "edit": {
            "kind": kind,
            "paragraph": paragraph,
            "old_text": old,
            "new_text": new,
        },
        "external_comment": external,
    }


def settled(**overrides):
    """Every point met or left uncovered, unless a test says otherwise."""
    replies = {
        "Limited use": [verdict("meets", paragraphs=["P3"], quote=USE)],
        "Compelled disclosure": [verdict("meets", paragraphs=["P4"], quote=NOTICE)],
        "Oral information": [verdict("meets", paragraphs=["P2"], quote=ORAL)],
        "Term": [verdict("not_covered")],
    }
    replies.update(overrides)
    return replies


class ScriptedModel:
    """Replies in order, one per call, by the point asked about, and keeps what it was asked."""

    name = "scripted"
    window = 32_768
    concurrency = 1

    def __init__(self, replies: dict[str, list[dict | str]]):
        self.replies = replies
        self.asked: list[list[tuple[str, str]]] = []

    def ask(self, system, turns, schema, shared):
        self.asked.append(turns)
        point = turns[0][1].split("Point:")[-1]
        title = next(t for t in self.replies if t in point)
        reply = self.replies[title].pop(0)
        return ModelReply(
            reply if isinstance(reply, str) else json.dumps(reply), 100, 20
        )

    def asked_about(self, title: str) -> list[list[tuple[str, str]]]:
        return [
            turns for turns in self.asked if title in turns[0][1].split("Point:")[-1]
        ]


class Checker:
    name = "checker"
    window = 32_768
    concurrency = 1

    def __init__(self, supported: bool, missing: str = ""):
        self.reply = {"supported": supported, "missing": missing}
        self.asked = 0

    def ask(self, system, turns, schema, shared):
        self.asked += 1
        return ModelReply(json.dumps(self.reply), 50, 10)


def by_key(result):
    """Each point's result by its key."""
    return {r.point.key: r for r in result.results}


def applied(contract: Path, result, tmp_path: Path) -> RedlinedWord:
    """The runner's operations applied as the revise pipeline applies them: all or nothing."""
    out = tmp_path / "revised.docx"
    report = word.apply(contract, result.operations, out)
    assert report.saved, report.outcomes
    return RedlinedWord(out.read_bytes())


def external_copy(contract: Path, result, tmp_path: Path) -> RedlinedWord:
    """What the other side gets: the copy without SurfSense's internal comments."""
    out = tmp_path / "revised.docx"
    report = word.apply(contract, result.operations, out)
    internal = [
        outcome.values["comment_id"]
        for op, outcome in zip(result.operations, report.outcomes, strict=True)
        if op.get("internal") and "comment_id" in outcome.values
    ]
    shared = tmp_path / "external.docx"
    word.external(out, shared, internal)
    return RedlinedWord(shared.read_bytes())


def test_a_deviation_becomes_a_tracked_change_with_its_comments(
    config, contract, tmp_path
):
    """A deviation is a tracked change by SurfSense, with the reason the other side reads and SurfSense's reasoning with the playbook quote, which the other side's copy leaves out."""
    model = ScriptedModel(
        settled(
            **{
                "Compelled disclosure": [
                    verdict(
                        "deviates",
                        paragraphs=["P4"],
                        quote=NOTICE,
                        kind="replace",
                        paragraph="P4",
                        old="may disclose Confidential Information when required by law",
                        new="may disclose Confidential Information when required by law, "
                        "after giving the Disclosing Party prompt written notice",
                        external="We ask for notice before any compelled disclosure.",
                        internal="The contract allows a compelled disclosure without notice.",
                    )
                ]
            }
        )
    )

    result = review_contract(contract, [PLAYBOOK], config, model)

    point = by_key(result)["compelled-disclosure"]
    assert point.verdict == "changed"
    assert point.paragraphs == ["P4"]
    revised = applied(contract, result, tmp_path)
    assert [i.text for i in revised.insertions] == [
        ", after giving the Disclosing Party prompt written notice"
    ]
    assert {i.author for i in revised.insertions} == {"SurfSense"}
    comments = [c.text for c in revised.comments]
    assert "We ask for notice before any compelled disclosure." in comments
    assert any(NOTICE in c and "Compelled disclosure" in c for c in comments)
    # The other side reads the change and its reason, never SurfSense's reasoning.
    other_side = [c.text for c in external_copy(contract, result, tmp_path).comments]
    assert other_side == ["We ask for notice before any compelled disclosure."]


def test_a_missing_term_is_inserted_after_the_paragraph_named(
    config, contract, tmp_path
):
    """A term the playbook requires and the contract lacks is a new paragraph after the one named."""
    added = "Information disclosed orally is Confidential Information if identified as confidential when disclosed."
    model = ScriptedModel(
        settled(
            **{
                "Oral information": [
                    verdict(
                        "missing",
                        paragraphs=["P2"],
                        quote=ORAL,
                        kind="insert_after",
                        paragraph="P2",
                        new=added,
                        external="Oral disclosures should be covered too.",
                    )
                ]
            }
        )
    )

    result = review_contract(contract, [PLAYBOOK], config, model)

    assert by_key(result)["oral"].verdict == "changed"
    paragraphs = applied(contract, result, tmp_path).paragraphs
    assert paragraphs[2] == added
    assert paragraphs[1].startswith("“Confidential Information” means")


def test_a_contract_that_already_meets_the_playbook_still_saves_a_version(
    config, contract, tmp_path
):
    """With nothing to change, the summary comment alone still makes a version, and changes no text."""
    model = ScriptedModel(settled())

    result = review_contract(contract, [PLAYBOOK], config, model)

    assert result.counts == {
        "changed": 0,
        "meets": 3,
        "not_covered": 1,
        "for_person": 0,
        "skipped": 0,
    }
    assert [op["op"] for op in result.operations] == ["add_comment"]
    assert result.operations[0]["internal"] is True
    revised = applied(contract, result, tmp_path)
    assert revised.insertions == [] and revised.deletions == []
    assert "3 meet" in revised.comments[0].text


def test_a_change_whose_playbook_quote_is_not_found_goes_to_a_person(
    config, contract, tmp_path
):
    """No change stands on a playbook quote that is not in the playbook: asked again once with the passage it cited, then left to a person."""
    invented = verdict(
        "deviates",
        paragraphs=["P4"],
        quote="The Receiving Party must notify the Disclosing Party within five days",
        kind="replace",
        paragraph="P4",
        old="when required by law",
        new="when required by law, after five days' notice",
    )
    model = ScriptedModel(
        settled(**{"Compelled disclosure": [invented, dict(invented)]})
    )

    result = review_contract(contract, [PLAYBOOK], config, model)

    point = by_key(result)["compelled-disclosure"]
    assert point.verdict == "for_person"
    assert "QUOTE_NOT_FOUND" in point.codes
    # Asked once more, shown the playbook's nearest real sentence.
    asked = model.asked_about("Compelled disclosure")
    assert len(asked) == 2
    assert "prompt written notice" in asked[1][-1][1]
    revised = applied(contract, result, tmp_path)
    assert revised.insertions == []
    assert any("Compelled disclosure" in c.text for c in revised.comments)


def test_old_text_that_is_not_in_the_paragraph_named_goes_to_a_person(
    config, contract, tmp_path
):
    """A change to words the paragraph does not hold is never forced: after one more ask it goes to a person."""
    wrong = verdict(
        "deviates",
        paragraphs=["P4"],
        quote=NOTICE,
        kind="replace",
        paragraph="P4",
        old="may share Confidential Information with anyone",
        new="may share Confidential Information after notice",
    )
    model = ScriptedModel(settled(**{"Compelled disclosure": [wrong, dict(wrong)]}))

    result = review_contract(contract, [PLAYBOOK], config, model)

    point = by_key(result)["compelled-disclosure"]
    assert point.verdict == "for_person"
    assert "TEXT_NOT_FOUND" in point.codes
    assert applied(contract, result, tmp_path).insertions == []


def test_straight_quotes_and_a_list_label_in_old_text_still_place_the_change(
    config, contract, tmp_path
):
    """Straight quotes for curly ones and the clause's number at the front still find the words, and only what differs is marked."""
    model = ScriptedModel(
        settled(
            **{
                "Oral information": [
                    verdict(
                        "deviates",
                        paragraphs=["P2"],
                        quote=ORAL,
                        kind="replace",
                        paragraph="P2",
                        old='1. "Confidential Information" means information disclosed in writing',
                        new='"Confidential Information" means information disclosed in writing or orally',
                    )
                ]
            }
        )
    )

    result = review_contract(contract, [PLAYBOOK], config, model)

    assert by_key(result)["oral"].verdict == "changed"
    revised = applied(contract, result, tmp_path)
    assert [i.text.strip() for i in revised.insertions] == ["or orally"]
    assert revised.deletions == []
    assert revised.paragraphs[1].startswith(
        "“Confidential Information” means information disclosed in writing or orally and"
    )


def test_the_model_reads_each_clause_with_its_list_number(config, contract):
    """Each clause is shown by its id with the number Word shows, apart from its text."""
    model = ScriptedModel(settled())

    review_contract(contract, [PLAYBOOK], config, model)

    first = model.asked[0][0][1]
    assert "[P1] MUTUAL NON-DISCLOSURE AGREEMENT" in first
    assert "[P3 | 2.] The Receiving Party shall use Confidential Information" in first


def test_of_two_changes_to_the_same_words_the_first_in_the_paragraph_is_made(
    config, contract, tmp_path
):
    """Two changes to the same words: the first in the paragraph is made, the other goes to a person, and the operations all apply."""
    model = ScriptedModel(
        settled(
            **{
                "Compelled disclosure": [
                    verdict(
                        "deviates",
                        paragraphs=["P4"],
                        quote=NOTICE,
                        kind="replace",
                        paragraph="P4",
                        old="when required by law",
                        new="when a court orders it",
                    )
                ],
                # Quotes words the change above deletes, so they no longer read.
                "Limited use": [
                    verdict(
                        "deviates",
                        paragraphs=["P4"],
                        quote=USE,
                        kind="replace",
                        paragraph="P4",
                        old="required by law",
                        new="required by law or regulation",
                    )
                ],
            }
        )
    )

    result = review_contract(contract, [PLAYBOOK], config, model)

    points = by_key(result)
    assert points["compelled-disclosure"].verdict == "changed"
    assert points["use"].verdict == "for_person"
    assert points["use"].codes == ["CHANGES_OVERLAP"]
    assert [i.text for i in applied(contract, result, tmp_path).insertions] == [
        "a court orders it"
    ]


def test_a_change_the_checker_does_not_support_goes_to_a_person(contract, tmp_path):
    """A change the second check does not find called for is not made; only changes are checked."""
    config = load_config(write_config(tmp_path, check=True))
    model = ScriptedModel(
        settled(
            **{
                "Compelled disclosure": [
                    verdict(
                        "deviates",
                        paragraphs=["P4"],
                        quote=NOTICE,
                        kind="replace",
                        paragraph="P4",
                        old="when required by law",
                        new="when required by law and the Disclosing Party consents",
                    )
                ]
            }
        )
    )
    checker = Checker(False, "The playbook asks for notice, not consent.")

    result = review_contract(contract, [PLAYBOOK], config, model, checker=checker)

    point = by_key(result)["compelled-disclosure"]
    assert point.verdict == "for_person"
    assert "NOT_SUPPORTED" in point.codes
    assert checker.asked == 1  # changes alone are checked
    assert applied(contract, result, tmp_path).insertions == []


def test_with_explanations_to_the_other_side_off_every_comment_stays_internal(
    config, contract, tmp_path
):
    """With the firm's setting off, every comment is internal, so the other side's copy has none."""
    model = ScriptedModel(
        settled(
            **{
                "Compelled disclosure": [
                    verdict(
                        "deviates",
                        paragraphs=["P4"],
                        quote=NOTICE,
                        kind="replace",
                        paragraph="P4",
                        old="when required by law",
                        new="when required by law, after prompt written notice",
                        external="We ask for notice first.",
                    )
                ]
            }
        )
    )

    result = review_contract(
        contract, [PLAYBOOK], config, model, settings={"external_comments": False}
    )

    assert by_key(result)["compelled-disclosure"].verdict == "changed"
    assert all(
        op.get("internal")
        for op in result.operations
        if op.get("comment") or op["op"] == "add_comment"
    )
    assert external_copy(contract, result, tmp_path).comments == []


def test_an_unreadable_reply_is_asked_again_once(config, contract):
    """A reply that is not the JSON asked for is asked again once."""
    model = ScriptedModel(
        settled(**{"Term": ["I think it is fine.", verdict("not_covered")]})
    )

    result = review_contract(contract, [PLAYBOOK], config, model)

    assert by_key(result)["term"].verdict == "not_covered"
    assert len(model.asked_about("Term")) == 2


def test_a_cancel_stops_the_run(config, contract):
    """A cancel stops the run as a cancel, not a failure."""
    with pytest.raises(FillStoppedError):
        review_contract(
            contract, [PLAYBOOK], config, ScriptedModel(settled()), stop=lambda: True
        )


def test_a_contract_with_no_text_is_refused_before_any_call(config, tmp_path):
    """A contract with no text is refused before any model call."""
    empty = tmp_path / "Empty.docx"
    docx.Document().save(empty)
    model = ScriptedModel(settled())

    with pytest.raises(NoClausesError):
        review_contract(empty, [PLAYBOOK], config, model)
    assert model.asked == []


def test_two_changes_to_different_words_of_one_paragraph_are_both_made(
    config, contract, tmp_path
):
    """Each change is narrowed to the words it alters before it is placed, so a model that
    quotes most of a paragraph does not crowd out another point's change to it."""
    model = ScriptedModel(
        settled(
            **{
                "Compelled disclosure": [
                    verdict(
                        "deviates",
                        paragraphs=["P4"],
                        quote=NOTICE,
                        kind="replace",
                        paragraph="P4",
                        old="may disclose Confidential Information when required by law",
                        new="may disclose Confidential Information when required by law, "
                        "after prompt written notice",
                    )
                ],
                "Limited use": [
                    verdict(
                        "deviates",
                        paragraphs=["P4"],
                        quote=USE,
                        kind="replace",
                        paragraph="P4",
                        old="The Receiving Party may disclose Confidential Information",
                        new="The Receiving Party may only disclose Confidential Information",
                    )
                ],
            }
        )
    )

    result = review_contract(contract, [PLAYBOOK], config, model)

    points = by_key(result)
    assert (points["compelled-disclosure"].verdict, points["use"].verdict) == (
        "changed",
        "changed",
    )
    revised = applied(contract, result, tmp_path)
    assert sorted(i.text for i in revised.insertions) == [
        ", after prompt written notice",
        "only ",
    ]
