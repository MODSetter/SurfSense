"""Pairing a model on disk with the projector that belongs to it."""

from pathlib import Path

import pytest

from modules.llm.providers.llamacpp import projector_for

pytestmark = pytest.mark.unit


def touch(path: Path) -> Path:
    """A file on disk. Pairing reads names and sizes, never contents."""
    path.write_bytes(b"GGUF")
    return path


def test_the_pair_is_found_by_name_whichever_way_it_is_written() -> None:
    """Finding the pair is a directory search, so it stays a name match: a
    header read per file is the cost this avoids. What a file *is* is decided
    from its header in `gguf/file_kind.py`, and `reprice` asks there before
    offering anything as a model, so a badly named projector is caught even
    though this never sees it."""
    from modules.llm.providers.llamacpp.projector import _named_as_projector

    assert _named_as_projector(Path("mmproj-F16.gguf"))
    assert _named_as_projector(Path("Qwen3-VL-mmproj-BF16.gguf"))
    assert not _named_as_projector(Path("Qwen3-8B-Q4_K_M.gguf"))


def test_the_manifest_name_wins_when_there_is_one(tmp_path: Path) -> None:
    """A curated entry states its projector exactly, so nothing is inferred."""
    model = touch(tmp_path / "Qwen3-VL-Q4_K_M.gguf")
    named = touch(tmp_path / "mmproj-F16.gguf")
    touch(tmp_path / "mmproj-Q8_0.gguf")

    assert projector_for(model, ["mmproj-F16.gguf"]) == named


def test_a_searched_model_takes_the_one_projector_beside_it(tmp_path: Path) -> None:
    """No manifest row to consult, and exactly one candidate."""
    model = touch(tmp_path / "Some-VL-Q4_K_M.gguf")
    projector = touch(tmp_path / "mmproj-F16.gguf")

    assert projector_for(model) == projector


def test_two_projectors_with_nothing_to_choose_between_them_pair_with_neither(
    tmp_path: Path,
) -> None:
    """They belong to two different models. Guessing attaches the wrong one, and
    a wrong projector is worse than none: the model answers, badly, about images
    it never really saw."""
    model = touch(tmp_path / "Some-VL-Q4_K_M.gguf")
    touch(tmp_path / "mmproj-F16.gguf")
    touch(tmp_path / "other-mmproj-F16.gguf")

    assert projector_for(model) is None


def test_a_text_model_alone_in_a_directory_has_none(tmp_path: Path) -> None:
    """The common case, and it must not cost a reserve."""
    model = touch(tmp_path / "Qwen3-8B-Q4_K_M.gguf")

    assert projector_for(model) is None


def test_a_manifest_name_that_is_not_on_disk_falls_through(tmp_path: Path) -> None:
    """The weights downloaded and the projector did not, so the model still runs
    as text rather than naming a file the worker cannot open."""
    model = touch(tmp_path / "Qwen3-VL-Q4_K_M.gguf")

    assert projector_for(model, ["mmproj-F16.gguf"]) is None
