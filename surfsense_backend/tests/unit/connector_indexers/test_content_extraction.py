"""Tests that each cloud connector's download_and_extract_content correctly
produces markdown from a real file via the unified ETL pipeline.

Only the cloud client is mocked (system boundary).  The ETL pipeline runs for
real so we know the full path from "cloud gives us bytes" to "we get markdown
back" actually works.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit

_TXT_CONTENT = "Hello from the cloud connector test."
_CSV_CONTENT = "name,age\nAlice,30\nBob,25\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _write_file(dest_path: str, content: str) -> None:
    """Simulate a cloud client writing downloaded bytes to disk."""
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(content)


def _make_download_side_effect(content: str):
    """Return an async side-effect that writes *content* to the dest path
    and returns ``None`` (success)."""

    async def _side_effect(*args):
        dest_path = args[-1]
        await _write_file(dest_path, content)
        return None

    return _side_effect


# ===================================================================
# Google Drive
# ===================================================================


class TestGoogleDriveContentExtraction:
    async def test_txt_file_returns_markdown(self):
        from app.connectors.google_drive.content_extractor import (
            download_and_extract_content,
        )

        client = MagicMock()
        client.download_file_to_disk = AsyncMock(
            side_effect=_make_download_side_effect(_TXT_CONTENT),
        )

        file = {"id": "f1", "name": "notes.txt", "mimeType": "text/plain"}

        markdown, metadata, error = await download_and_extract_content(client, file)

        assert error is None
        assert _TXT_CONTENT in markdown
        assert metadata["google_drive_file_id"] == "f1"
        assert metadata["google_drive_file_name"] == "notes.txt"

    async def test_csv_file_returns_markdown_table(self):
        from app.connectors.google_drive.content_extractor import (
            download_and_extract_content,
        )

        client = MagicMock()
        client.download_file_to_disk = AsyncMock(
            side_effect=_make_download_side_effect(_CSV_CONTENT),
        )

        file = {"id": "f2", "name": "data.csv", "mimeType": "text/csv"}

        markdown, _metadata, error = await download_and_extract_content(client, file)

        assert error is None
        assert "Alice" in markdown
        assert "Bob" in markdown
        assert "|" in markdown

    async def test_download_error_returns_error_message(self):
        from app.connectors.google_drive.content_extractor import (
            download_and_extract_content,
        )

        client = MagicMock()
        client.download_file_to_disk = AsyncMock(return_value="Network timeout")

        file = {"id": "f3", "name": "doc.txt", "mimeType": "text/plain"}

        markdown, _metadata, error = await download_and_extract_content(client, file)

        assert markdown is None
        assert error == "Network timeout"


# ===================================================================
# OneDrive
# ===================================================================


class TestOneDriveContentExtraction:
    async def test_txt_file_returns_markdown(self):
        from app.connectors.onedrive.content_extractor import (
            download_and_extract_content,
        )

        client = MagicMock()
        client.download_file_to_disk = AsyncMock(
            side_effect=_make_download_side_effect(_TXT_CONTENT),
        )

        file = {
            "id": "od-1",
            "name": "report.txt",
            "file": {"mimeType": "text/plain"},
        }

        markdown, metadata, error = await download_and_extract_content(client, file)

        assert error is None
        assert _TXT_CONTENT in markdown
        assert metadata["onedrive_file_id"] == "od-1"
        assert metadata["onedrive_file_name"] == "report.txt"

    async def test_csv_file_returns_markdown_table(self):
        from app.connectors.onedrive.content_extractor import (
            download_and_extract_content,
        )

        client = MagicMock()
        client.download_file_to_disk = AsyncMock(
            side_effect=_make_download_side_effect(_CSV_CONTENT),
        )

        file = {
            "id": "od-2",
            "name": "data.csv",
            "file": {"mimeType": "text/csv"},
        }

        markdown, _metadata, error = await download_and_extract_content(client, file)

        assert error is None
        assert "Alice" in markdown
        assert "|" in markdown

    async def test_download_error_returns_error_message(self):
        from app.connectors.onedrive.content_extractor import (
            download_and_extract_content,
        )

        client = MagicMock()
        client.download_file_to_disk = AsyncMock(return_value="403 Forbidden")

        file = {
            "id": "od-3",
            "name": "secret.txt",
            "file": {"mimeType": "text/plain"},
        }

        markdown, _metadata, error = await download_and_extract_content(client, file)

        assert markdown is None
        assert error == "403 Forbidden"


# ===================================================================
# Dropbox
# ===================================================================


class TestDropboxContentExtraction:
    async def test_txt_file_returns_markdown(self):
        from app.connectors.dropbox.content_extractor import (
            download_and_extract_content,
        )

        client = MagicMock()
        client.download_file_to_disk = AsyncMock(
            side_effect=_make_download_side_effect(_TXT_CONTENT),
        )

        file = {
            "id": "dbx-1",
            "name": "memo.txt",
            ".tag": "file",
            "path_lower": "/memo.txt",
        }

        markdown, metadata, error = await download_and_extract_content(client, file)

        assert error is None
        assert _TXT_CONTENT in markdown
        assert metadata["dropbox_file_id"] == "dbx-1"
        assert metadata["dropbox_file_name"] == "memo.txt"

    async def test_csv_file_returns_markdown_table(self):
        from app.connectors.dropbox.content_extractor import (
            download_and_extract_content,
        )

        client = MagicMock()
        client.download_file_to_disk = AsyncMock(
            side_effect=_make_download_side_effect(_CSV_CONTENT),
        )

        file = {
            "id": "dbx-2",
            "name": "data.csv",
            ".tag": "file",
            "path_lower": "/data.csv",
        }

        markdown, _metadata, error = await download_and_extract_content(client, file)

        assert error is None
        assert "Alice" in markdown
        assert "|" in markdown

    async def test_download_error_returns_error_message(self):
        from app.connectors.dropbox.content_extractor import (
            download_and_extract_content,
        )

        client = MagicMock()
        client.download_file_to_disk = AsyncMock(return_value="Rate limited")

        file = {
            "id": "dbx-3",
            "name": "big.txt",
            ".tag": "file",
            "path_lower": "/big.txt",
        }

        markdown, _metadata, error = await download_and_extract_content(client, file)

        assert markdown is None
        assert error == "Rate limited"
