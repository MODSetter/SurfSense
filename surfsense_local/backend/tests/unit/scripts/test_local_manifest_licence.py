"""The licence rule: every curated model allows commercial use, uncapped."""

import pytest
from local_manifest.entries import ENTRIES
from local_manifest.entry import Entry
from local_manifest.licence import refused

from modules.llm.catalog.local.manifest import load_local_manifest

pytestmark = pytest.mark.unit


def _entry(license: str) -> Entry:
    return Entry(
        id="some-model",
        name="Some Model",
        family="Some",
        publisher="Someone",
        description="A model.",
        license=license,
        source_repo="someone/some-model",
        repo="someone/some-model-GGUF",
    )


def test_a_non_commercial_licence_is_refused_by_name() -> None:
    """The refusal names the model and its licence, so a person can act on it."""
    (problem,) = refused([_entry("sai-nc-community")])

    assert "some-model" in problem
    assert "sai-nc-community" in problem


def test_an_apache_licence_passes() -> None:
    """Most curated weights are Apache-2.0."""
    assert refused([_entry("apache-2.0")]) == []


def test_every_entry_the_refresh_reads_passes() -> None:
    """The refresh refuses to start otherwise."""
    assert refused(ENTRIES) == []


def test_every_committed_model_passes() -> None:
    """A hand edit to the manifest is held to the same rule as a refresh."""
    assert refused(load_local_manifest().models) == []
