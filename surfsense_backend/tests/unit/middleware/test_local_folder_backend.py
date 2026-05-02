from pathlib import Path

import pytest

from app.agents.new_chat.middleware.local_folder_backend import LocalFolderBackend

pytestmark = pytest.mark.unit


def test_local_backend_write_read_edit_roundtrip(tmp_path: Path):
    backend = LocalFolderBackend(str(tmp_path))
    (tmp_path / "notes").mkdir()

    write = backend.write("/notes/test.md", "line1\nline2")
    assert write.error is None
    assert write.path == "/notes/test.md"

    read = backend.read("/notes/test.md", offset=0, limit=20)
    assert "line1" in read
    assert "line2" in read

    edit = backend.edit("/notes/test.md", "line2", "updated")
    assert edit.error is None
    assert edit.occurrences == 1

    read_after = backend.read("/notes/test.md", offset=0, limit=20)
    assert "updated" in read_after


def test_local_backend_blocks_path_escape(tmp_path: Path):
    backend = LocalFolderBackend(str(tmp_path))

    result = backend.write("/../../etc/passwd", "bad")
    assert result.error is not None
    assert "Invalid path" in result.error


def test_local_backend_glob_and_grep(tmp_path: Path):
    backend = LocalFolderBackend(str(tmp_path))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.txt").write_text("hello world\n")
    (tmp_path / "docs" / "b.md").write_text("hello markdown\n")

    infos = backend.glob_info("**/*.txt", "/docs")
    paths = {info["path"] for info in infos}
    assert "/docs/a.txt" in paths

    grep = backend.grep_raw("hello", "/docs", "*.md")
    assert isinstance(grep, list)
    assert any(match["path"] == "/docs/b.md" for match in grep)


def test_local_backend_read_raw_returns_exact_content(tmp_path: Path):
    backend = LocalFolderBackend(str(tmp_path))
    (tmp_path / "notes").mkdir()
    expected = "# Title\n\nline 1\nline 2\n"
    write = backend.write("/notes/raw.md", expected)
    assert write.error is None

    raw = backend.read_raw("/notes/raw.md")
    assert raw == expected


def test_local_backend_write_rejects_missing_parent_directory(tmp_path: Path):
    backend = LocalFolderBackend(str(tmp_path))

    write = backend.write("/tempoo/new-note.md", "# New note")

    assert write.error is not None
    assert "parent directory" in write.error
    assert not (tmp_path / "tempoo").exists()


def test_local_backend_delete_file_success(tmp_path: Path):
    backend = LocalFolderBackend(str(tmp_path))
    (tmp_path / "delete-me.md").write_text("bye")

    res = backend.delete_file("/delete-me.md")
    assert res.error is None
    assert res.path == "/delete-me.md"
    assert not (tmp_path / "delete-me.md").exists()


def test_local_backend_delete_file_rejects_directory(tmp_path: Path):
    backend = LocalFolderBackend(str(tmp_path))
    (tmp_path / "subdir").mkdir()

    res = backend.delete_file("/subdir")
    assert res.error is not None
    assert "directory" in res.error
    assert (tmp_path / "subdir").exists()


def test_local_backend_delete_file_missing_returns_error(tmp_path: Path):
    backend = LocalFolderBackend(str(tmp_path))

    res = backend.delete_file("/nope.md")
    assert res.error is not None
    assert "not found" in res.error


def test_local_backend_rmdir_success(tmp_path: Path):
    backend = LocalFolderBackend(str(tmp_path))
    (tmp_path / "empty").mkdir()

    res = backend.rmdir("/empty")
    assert res.error is None
    assert res.path == "/empty"
    assert not (tmp_path / "empty").exists()


def test_local_backend_rmdir_rejects_non_empty(tmp_path: Path):
    backend = LocalFolderBackend(str(tmp_path))
    (tmp_path / "withkid").mkdir()
    (tmp_path / "withkid" / "child.md").write_text("x")

    res = backend.rmdir("/withkid")
    assert res.error is not None
    assert "not empty" in res.error
    assert (tmp_path / "withkid" / "child.md").exists()


def test_local_backend_rmdir_rejects_file(tmp_path: Path):
    backend = LocalFolderBackend(str(tmp_path))
    (tmp_path / "f.md").write_text("x")

    res = backend.rmdir("/f.md")
    assert res.error is not None
    assert "not a directory" in res.error


def test_local_backend_rmdir_rejects_root(tmp_path: Path):
    """``rmdir /`` MUST fail. The exact error wording comes from
    ``_resolve_virtual`` (root resolves to outside the sandbox); what
    matters is that the call returns an error and does NOT delete the
    sandbox root on disk."""
    backend = LocalFolderBackend(str(tmp_path))

    res = backend.rmdir("/")
    assert res.error is not None
    assert "Invalid path" in res.error or "root" in res.error
    assert tmp_path.exists()
