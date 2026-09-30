"""Whether a remote model reads images, one answer for every place that asks."""

import pytest

from modules.llm.catalog.remote.reads_images import remote_reads_images

pytestmark = pytest.mark.unit


def test_a_provider_entry_that_takes_images_reads_them() -> None:
    """`image` among the entry's inputs."""
    assert remote_reads_images("gpt-4o", "openai")


def test_a_text_only_entry_does_not() -> None:
    """A known model that takes text alone."""
    assert not remote_reads_images("gpt-3.5-turbo", "openai")


def test_a_custom_connection_reads_the_makers_entry() -> None:
    """`custom` names no provider, so the id is looked up across the manifest."""
    assert remote_reads_images("openai/gpt-4o", "custom")


def test_an_id_the_manifest_does_not_carry_answers_no() -> None:
    """Attach would otherwise be offered to a model nothing says can see."""
    assert not remote_reads_images("nope/nothing", "custom")
