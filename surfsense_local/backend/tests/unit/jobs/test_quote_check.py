"""A quote stands only when its words are in a source, in order; numbers and negations count."""

import pytest

from modules.jobs.provenance.quote_check import find_quote, nearest_sentence

pytestmark = pytest.mark.unit

PLAN = """## Section IV — Access

Access to taxpayer data is granted on a **least-privilege** basis.
Laptops are encrypted with BitLocker; incidents are reported within 72 hours.

Paper records are shredded when no longer needed."""


@pytest.mark.parametrize(
    "quote",
    [
        "Access to taxpayer data is granted on a least-privilege basis.",
        "access to TAXPAYER data is granted on a “least privilege” basis",
        "Laptops are encrypted with BitLocker ... reported within 72 hours",
    ],
)
def test_a_quote_found_word_for_word_stands_wherever_its_marks_differ(quote):
    """Case, quotes, emphasis and an ellipsis between parts do not stop a true quote matching."""
    found = find_quote(quote, ["Other text entirely.", PLAN])

    assert found is not None and found.source == 1


@pytest.mark.parametrize(
    "quote",
    [
        "incidents are reported within 24 hours",
        "Laptops are not encrypted with BitLocker",
        "Access to client data is granted on a least-privilege basis.",
        "least privilege",
        "Laptops are encrypted ... 72",
    ],
)
def test_a_quote_that_changes_a_word_number_or_negation_does_not(quote):
    """A changed number, an added not, another word or a part too short never matches."""
    assert find_quote(quote, [PLAN]) is None


def test_the_line_found_is_where_the_quote_starts():
    """The line given is where the quote starts, for the answer's source."""
    found = find_quote("Paper records are shredded", [PLAN])

    assert found is not None and found.line == 6


def test_a_loose_copy_is_shown_the_sentence_it_most_likely_meant():
    """A paraphrase of a real sentence gets that sentence back, as the source writes it; words
    that are not close to any sentence get nothing."""
    loose = "Access to taxpayer data is granted on a least privilege principle."

    assert nearest_sentence(loose, ["Other text entirely.", PLAN]) == (
        "Access to taxpayer data is granted on a **least-privilege** basis."
    )
    assert nearest_sentence("Backups are tested every quarter offsite.", [PLAN]) is None


def test_a_link_reads_as_its_text_and_far_apart_parts_are_not_one_quote():
    """A quote of a sentence holding a link matches without the link's target; parts joined by
    "..." must sit within a few hundred words of each other."""
    linked = (
        "Policies follow the [Controlled Document Procedure](/handbook/cdp/) yearly."
    )
    far = "Access is logged daily." + " filler" * 400 + " Keys rotate every year."

    assert find_quote("follow the Controlled Document Procedure yearly", [linked])
    assert (
        find_quote("Access is logged daily ... Keys rotate every year", [far]) is None
    )
    assert (
        find_quote("Keys rotate every year ... Access is logged daily", [far]) is None
    )


def test_a_quote_may_not_skip_a_negation_and_a_hint_never_turns_a_claim_around():
    """ "... " can leave words out, but not a "not"; the closest-sentence hint never offers a
    sentence that differs from the quote by a negation or a number."""
    source = "Customer data is not encrypted at rest. Backups are kept for a year."

    assert find_quote("Customer data is ... encrypted at rest", [source]) is None
    assert find_quote("Customer data is not encrypted ... kept for a year", [source])
    assert nearest_sentence("Customer data is encrypted at rest", [source]) is None
    assert nearest_sentence("Backups are kept for 2 years", [source]) is None


def test_a_line_of_brackets_is_read_in_linear_time():
    """A source line of many "[" and no "]" does not stall the check."""
    import time

    started = time.monotonic()
    find_quote("words that are not there", ["[" * 50_000])

    assert time.monotonic() - started < 2


def test_parts_repeated_with_a_negation_between_each_are_not_tried_every_way():
    """A quote whose parts recur all through a source, a "not" between each, fits nowhere
    and could be placed millions of ways: it counts as not found once a few thousand have
    been tried, instead of stalling the run."""
    import time

    parts = [
        "access is logged",
        "keys rotate yearly",
        "badges expire monthly",
        "laptops are encrypted",
        "backups are tested",
        "vendors are vetted",
    ]
    source = " not ".join(parts * 15)

    started = time.monotonic()
    found = find_quote(" ... ".join(parts), [source])

    assert found is None
    assert time.monotonic() - started < 2


def test_parts_that_recur_densely_early_do_not_hide_the_quote_further_on():
    """Parts repeated with a "not" between each, early in a source, do not use up the tries
    that find the quote where the source holds it whole."""
    import time

    parts = ["access is logged", "keys rotate yearly", "badges expire monthly"]
    source = (
        " not ".join(parts * 30)
        + " filler" * 400
        + "\naccess is logged and keys rotate yearly and badges expire monthly"
    )

    started = time.monotonic()
    found = find_quote(" ... ".join(parts), [source])

    assert found is not None and (found.line, found.end_line) == (2, 2)
    assert time.monotonic() - started < 2


def test_a_link_that_wraps_a_line_still_reads_as_its_text():
    """A Markdown link whose text breaks across lines matches a quote of the sentence."""
    source = (
        "Policies follow the [Controlled\nDocument Procedure](/handbook/cdp/) yearly."
    )

    found = find_quote("follow the Controlled Document Procedure yearly", [source])

    assert found is not None and found.line == 1


def test_every_part_of_a_quote_sits_within_the_window_of_every_other():
    """Two parts each near the first but far from each other are not one quote."""
    gap = " filler" * 250
    source = f"Access is logged daily.{gap} Keys rotate every year.{gap} Badges expire monthly."

    assert find_quote("Keys rotate every year ... Access is logged daily", [source])
    assert (
        find_quote(
            "Keys rotate every year ... Access is logged daily ... Badges expire monthly",
            [source],
        )
        is None
    )


@pytest.mark.parametrize(
    "quote",
    [
        "Access is logged daily ... Keys rotate every year",
        "Keys rotate every year ... Access is logged daily",
    ],
)
def test_a_quote_spans_from_the_part_the_source_gives_first(quote):
    """In either order, a quote's lines run from its earliest part in the source to its last,
    so the second check is shown every word between them."""
    source = "Access is logged daily.\nfiller\nfiller\nKeys rotate every year."

    found = find_quote(quote, [source])

    assert found is not None and (found.line, found.end_line) == (1, 4)
