"""Unit tests for scan_folder() pure logic — Tier 2 TDD slices (S1-S4)."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestScanFolder:
    """S1-S4: scan_folder() with real tmp_path filesystem."""

    def test_s1_single_md_file(self, tmp_path: Path):
        """S1: scan_folder on a dir with one .md file returns correct entry."""
        from app.tasks.connector_indexers.local_folder_indexer import scan_folder

        md = tmp_path / "note.md"
        md.write_text("# Hello")

        results = scan_folder(str(tmp_path))

        assert len(results) == 1
        entry = results[0]
        assert entry["relative_path"] == "note.md"
        assert entry["size"] > 0
        assert "modified_at" in entry
        assert entry["path"] == str(md)

    def test_s2_extension_filter(self, tmp_path: Path):
        """S2: file_extensions filter returns only matching files."""
        from app.tasks.connector_indexers.local_folder_indexer import scan_folder

        (tmp_path / "a.md").write_text("md")
        (tmp_path / "b.txt").write_text("txt")
        (tmp_path / "c.pdf").write_bytes(b"%PDF")

        results = scan_folder(str(tmp_path), file_extensions=[".md"])
        names = {r["relative_path"] for r in results}

        assert names == {"a.md"}

    def test_s3_exclude_patterns(self, tmp_path: Path):
        """S3: exclude_patterns skips files inside excluded directories."""
        from app.tasks.connector_indexers.local_folder_indexer import scan_folder

        (tmp_path / "good.md").write_text("good")
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "dep.js").write_text("module")
        git = tmp_path / ".git"
        git.mkdir()
        (git / "config").write_text("gitconfig")

        results = scan_folder(str(tmp_path), exclude_patterns=["node_modules", ".git"])
        names = {r["relative_path"] for r in results}

        assert "good.md" in names
        assert not any("node_modules" in n for n in names)
        assert not any(".git" in n for n in names)

    def test_s4_nested_dirs(self, tmp_path: Path):
        """S4: nested subdirectories produce correct relative paths."""
        from app.tasks.connector_indexers.local_folder_indexer import scan_folder

        daily = tmp_path / "notes" / "daily"
        daily.mkdir(parents=True)
        weekly = tmp_path / "notes" / "weekly"
        weekly.mkdir(parents=True)
        (daily / "today.md").write_text("today")
        (weekly / "review.md").write_text("review")
        (tmp_path / "root.txt").write_text("root")

        results = scan_folder(str(tmp_path))
        paths = {r["relative_path"] for r in results}

        assert "notes/daily/today.md" in paths or "notes\\daily\\today.md" in paths
        assert "notes/weekly/review.md" in paths or "notes\\weekly\\review.md" in paths
        assert "root.txt" in paths
