"""Electron's Word snapshot role, played by LibreOffice, so a live run's Word versions get page previews.

It speaks the same routes Electron polls (modules/agent/previews/router.py). The
pages come from LibreOffice's layout, not from docx-preview as in the app.
"""

import io
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

import docx
import httpx

SOFFICE = next(
    (
        path
        for path in (
            shutil.which("soffice"),
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            "/usr/bin/soffice",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        )
        if path and Path(path).is_file()
    ),
    None,
)
_SNAPSHOTS = "/agent/previews/docx-snapshots"
# Electron polls every 2 s; faster here leaves more of the tool's 30 s to print.
_POLL_SECONDS = 0.5
_PRINT_SECONDS = 25


class WordPrinter:
    """Polls the API for Word documents to print, while open."""

    def __init__(self, api_url: str) -> None:
        self._api = api_url
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._folder = Path(tempfile.mkdtemp(prefix="surfsense-live-print-"))
        self.printed = 0
        self.failures: list[str] = []
        # Why it does not poll: Word previews then say the desktop app is not running.
        self.unavailable: str | None = None

    def __enter__(self) -> "WordPrinter":
        # The first print builds LibreOffice's profile (about 7 s), which the tool's 30 s must not pay.
        blank = io.BytesIO()
        docx.Document().save(blank)
        try:
            self._to_pdf(blank.getvalue())
        except (OSError, subprocess.SubprocessError) as failure:
            self.unavailable = _reason(failure)
            return self
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stopping.set()
        if self.unavailable is None:
            self._thread.join(timeout=_PRINT_SECONDS + 5)
        shutil.rmtree(self._folder, ignore_errors=True)

    def summary(self) -> dict[str, Any]:
        """How the run's Word previews were printed, for its result.json."""
        return {
            "unavailable": self.unavailable,
            "printed": self.printed,
            "failures": self.failures,
        }

    def _serve(self) -> None:
        with httpx.Client(base_url=self._api, timeout=30.0) as api:
            while not self._stopping.wait(_POLL_SECONDS):
                try:
                    taken = api.get(f"{_SNAPSHOTS}/next")
                except httpx.HTTPError:
                    continue
                if taken.status_code == 200:
                    self._print(api, taken.json())

    def _print(self, api: httpx.Client, request: dict) -> None:
        try:
            word = api.get(request["file_url"])
            word.raise_for_status()
            pdf = self._to_pdf(word.content)
        except (httpx.HTTPError, OSError, subprocess.SubprocessError) as failure:
            reason = _reason(failure)
            self.failures.append(reason)
            api.post(f"{_SNAPSHOTS}/{request['id']}/failure", json={"reason": reason})
            return
        api.post(
            f"{_SNAPSHOTS}/{request['id']}/pdf",
            content=pdf,
            headers={"Content-Type": "application/pdf"},
        )
        self.printed += 1

    def _to_pdf(self, word: bytes) -> bytes:
        if SOFFICE is None:
            raise OSError("LibreOffice is not installed")
        source = self._folder / "document.docx"
        source.write_bytes(word)
        printed = self._folder / "document.pdf"
        printed.unlink(missing_ok=True)
        # A profile of its own, so a LibreOffice the user has open does not take the job.
        profile = (self._folder / "profile").as_uri()
        subprocess.run(
            [
                SOFFICE,
                f"-env:UserInstallation={profile}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(self._folder),
                str(source),
            ],
            check=True,
            capture_output=True,
            timeout=_PRINT_SECONDS,
        )
        return printed.read_bytes()


def _reason(failure: Exception) -> str:
    """Within the 500 characters the failure route takes."""
    return f"{type(failure).__name__}: {failure}"[:500]
