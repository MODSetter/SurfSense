"""The bundled model packs are named from their pins, and say that no licence text ships."""

import pytest
from notices.model_packs import model_notices

from modules.embedding.bundled import BGE
from modules.llm.transcription.voice_activity.model_file import (
    SILERO_VAD,
    VAD_DIR_NAME,
)

pytestmark = pytest.mark.unit


def test_every_pack_has_an_entry_with_a_licence_id_and_no_text():
    """Each pack names its licence and says no text ships, rather than invent one."""
    entries = [e for e in model_notices() if e["name"] != "Silero VAD"]
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


def test_silero_vad_ships_its_own_licence_text(tmp_path):
    """MIT asks for its notice beside every copy, and the pack carries the file."""
    staged = tmp_path / VAD_DIR_NAME
    staged.mkdir()
    (staged / SILERO_VAD.licence.name).write_text(
        "MIT License\n\nCopyright (c) Silero Team"
    )

    [vad] = [e for e in model_notices(tmp_path) if e["name"] == "Silero VAD"]

    assert (vad["license"], vad["version"]) == ("mit", SILERO_VAD.commit)
    assert vad["text"].startswith("MIT License")
    assert SILERO_VAD.repo in vad["note"]


def test_an_unstaged_vad_says_its_text_is_not_here(tmp_path):
    """A dev checkout that never fetched it still names the pack."""
    [vad] = [e for e in model_notices(tmp_path) if e["name"] == "Silero VAD"]

    assert vad["text"] == ""
    assert "not staged" in vad["note"]
