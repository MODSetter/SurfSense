"""What a reply earns against its case, by the eval's rules."""

import pytest
from chat_eval.cases import Case, Passage
from chat_eval.score import score

pytestmark = pytest.mark.unit

WARRANTY = Case(
    id="warranty",
    question="How long is the warranty on the Kestrel X200?",
    passages=[
        Passage(title="Returns policy", text="Unopened items return within 30 days."),
        Passage(title="Kestrel X200 manual", text="The X200 is covered for 27 months."),
        Passage(title="Kestrel X200 manual", text="The jar holds 1.8 litres."),
    ],
    supporting=[2],
    facts=["27"],
)


def test_a_reply_citing_its_supporting_passage_with_the_fact_passes() -> None:
    """The passage that holds the answer is cited, no other is, and the fact is there."""
    result = score(WARRANTY, "The X200 is covered for 27 months [2].", "stop")

    assert result.cites_support is True
    assert result.cites_other is False
    assert result.invented == 0
    assert result.facts is True


def test_a_label_that_names_no_passage_is_invented_and_supports_nothing() -> None:
    """Chat drops a label it cannot resolve, so the claim is left with no source."""
    result = score(WARRANTY, "The X200 is covered for 27 months [7].", "stop")

    assert result.invented == 1
    assert result.cites_support is False


def test_any_citation_on_an_unanswerable_case_cites_a_passage_that_misleads() -> None:
    """When no passage holds the answer, citing one passes it off as a source."""
    unanswerable = WARRANTY.model_copy(update={"supporting": [], "facts": []})

    result = score(unanswerable, "The sources do not say, but see [3].", "stop")

    assert result.cites_support is None
    assert result.cites_other is True
    assert result.facts is None


def test_a_thinking_model_that_spends_the_cap_on_reasoning_leaves_no_answer() -> None:
    """The cap counts reasoning tokens too, so the answer can be cut to nothing."""
    result = score(WARRANTY, "", "length")

    assert result.truncated is True
    assert result.empty is True


def test_a_hindi_question_answered_in_english_fails_the_language_check() -> None:
    """Chat asks for the question's language; the rule reads it from the script."""
    hindi = WARRANTY.model_copy(
        update={"question": "केस्ट्रेल X200 की वारंटी कितने महीने की है?"}
    )

    english = score(hindi, "The X200 is covered for 27 months [2].", "stop")
    in_hindi = score(hindi, "X200 की वारंटी 27 महीने की है [2]।", "stop")

    assert english.same_script is False
    assert in_hindi.same_script is True
