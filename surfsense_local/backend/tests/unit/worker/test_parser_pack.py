from pathlib import Path

import pytest

from worker.ingestion.parser_pack import (
    PARSER_FOLDERS,
    missing_parser_folders,
    parser_dir,
)

pytestmark = pytest.mark.unit


def test_missing_folders_lists_every_pack_piece(tmp_path: Path) -> None:
    """A half-copied pack must not look ready: ingest would then fail offline."""
    assert missing_parser_folders(tmp_path) == list(PARSER_FOLDERS)

    first = parser_dir(tmp_path) / PARSER_FOLDERS[0]
    first.mkdir(parents=True)
    (first / "weights").write_text("x")

    assert missing_parser_folders(tmp_path) == list(PARSER_FOLDERS[1:])


def test_empty_folder_is_not_a_pack(tmp_path: Path) -> None:
    """mkdir alone is not a download; snapshot_download leaves this on failure."""
    empty = parser_dir(tmp_path) / PARSER_FOLDERS[0]
    empty.mkdir(parents=True)

    assert PARSER_FOLDERS[0] in missing_parser_folders(tmp_path)


def test_complete_pack_is_empty_missing_list(tmp_path: Path) -> None:
    """The fetch script and the converter share this check."""
    root = parser_dir(tmp_path)
    for name in PARSER_FOLDERS:
        folder = root / name
        folder.mkdir(parents=True)
        (folder / "ok").write_text("1")

    assert missing_parser_folders(tmp_path) == []
