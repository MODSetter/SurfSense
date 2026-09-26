"""The committed manifest is the one every remote label comes from."""

import subprocess
import sys

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


def test_the_shipped_manifest_loads_without_the_system_encoding() -> None:
    """Windows reads cp1252 by default, and the manifest's UTF-8 left it empty."""
    load = (
        "from modules.llm.catalog.remote.manifest.loader import load_remote_manifest;"
        "load_remote_manifest()"
    )
    run = subprocess.run(
        [
            sys.executable,
            "-X",
            "warn_default_encoding",
            "-W",
            "error::EncodingWarning",
            "-c",
            load,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert run.returncode == 0, run.stderr


def test_the_shipped_manifest_knows_an_embedder_is_not_a_chat_model() -> None:
    """The old snapshot labelled text-embedding-3-small a chat model."""
    found = remote_lookup().classify("text-embedding-3-small", provider="openai")

    assert (found.known, found.types) == (True, frozenset())


def test_the_shipped_manifest_classifies_a_video_model() -> None:
    """The old snapshot had no word for video, so veo filled no slot."""
    found = remote_lookup().classify("veo-3.1-generate-preview", provider="google")

    assert ModelType.VIDEO_GEN in found.types
