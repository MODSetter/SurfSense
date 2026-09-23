"""The committed manifest is the one every remote label comes from."""

import pytest

from modules.llm.catalog.remote.manifest.loader import (
    load_remote_manifest,
    remote_lookup,
)
from modules.llm.model_type import ModelType

pytestmark = pytest.mark.unit


def test_the_shipped_manifest_loads() -> None:
    """A manifest that fails validation would cost every remote label."""
    manifest = load_remote_manifest()

    assert "openai" in manifest.providers
    assert "openrouter" in manifest.providers


def test_the_shipped_manifest_knows_an_embedder_is_not_a_chat_model() -> None:
    """The old snapshot labelled text-embedding-3-small a chat model."""
    found = remote_lookup().classify("text-embedding-3-small", provider="openai")

    assert (found.known, found.types) == (True, frozenset())


def test_the_shipped_manifest_classifies_a_video_model() -> None:
    """The old snapshot had no word for video, so veo filled no slot."""
    found = remote_lookup().classify("veo-3.1-generate-preview", provider="google")

    assert ModelType.VIDEO_GEN in found.types
