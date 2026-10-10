"""The bundled model packs are named from their pins, and say that no licence text ships."""

import pytest
from notices.model_packs import model_notices

from modules.embedding.bundled import BGE

pytestmark = pytest.mark.unit


def test_every_pack_has_an_entry_with_a_licence_id_and_no_text():
    """Each pack names its licence and says no text ships, rather than invent one."""
    entries = model_notices()
    assert {e["tree"] for e in entries} == {"model"}
    for entry in entries:
        assert entry["license"], entry["name"]
        assert entry["text"] == ""
        assert "no licence text ships" in entry["note"], entry["name"]


def test_the_embedder_is_named_at_its_pinned_revision():
    """The embedder's notice points at the exact weights the installer carries."""
    [bge] = [e for e in model_notices() if e["name"] == BGE.id]
    assert bge["version"] == BGE.revision
    assert BGE.repo in bge["note"]


def test_the_voice_takes_its_licence_from_the_manifest():
    """The voice's licence id is the one the curated manifest records."""
    [voice] = [e for e in model_notices() if e["name"].startswith("Kokoro")]
    assert voice["license"] == "apache-2.0"
