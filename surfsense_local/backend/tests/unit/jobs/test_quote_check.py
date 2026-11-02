"""A quote stands only when its words are in a source, in order; numbers and negations count."""

import pytest

from modules.jobs.provenance.quote_check import find_quote

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
