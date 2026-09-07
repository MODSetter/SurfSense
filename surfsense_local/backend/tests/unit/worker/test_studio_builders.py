"""Builders render deterministically, and the registry matches the API catalog."""

import pytest

from modules.artifacts.formats import FORMATS
from worker.studio.builders import BUILDERS
from worker.studio.builders.summary import build

pytestmark = pytest.mark.unit


def test_every_buildable_format_has_a_builder() -> None:
    """The dependency-free catalog and the worker registry cannot drift apart."""
    buildable = {fmt.key for fmt in FORMATS if not fmt.requires_key}
    assert set(BUILDERS) == buildable


def test_a_summary_takes_its_title_from_the_first_h1() -> None:
    """The document title comes from the model's H1, so the list reads well."""
    built = build("# Saturn's rings\n\nThey are mostly ice.", [])

    assert built.title == "Saturn's rings"
    assert built.markdown.startswith("# Saturn's rings")
    assert built.primary is None  # the markdown is the body, not a file


def test_a_summary_without_a_heading_still_has_a_title() -> None:
    """A model that skips the H1 still yields a named, openable artifact."""
    assert build("Just prose, no heading.", []).title == "Summary"
