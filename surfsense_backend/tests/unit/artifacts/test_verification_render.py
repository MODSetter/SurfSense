from __future__ import annotations

import pytest

from app.artifacts.verification import render
from app.sandbox import ExecResult
from tests.utils.fake_sandbox import FakeSandboxSession


class RecordingSession(FakeSandboxSession):
    def __init__(self, *, fail_step: str | None = None) -> None:
        self.fail_step = fail_step
        super().__init__(command_handler=self._command)

    def _command(self, command: str) -> ExecResult:
        if self.fail_step and self.fail_step in command:
            return ExecResult("conversion error", 1)
        if "set --" in command:
            build_dir = command.split("set -- ", 1)[1].split("/page-", 1)[0]
            return ExecResult(f"{build_dir}/page-1.jpg\n{build_dir}/page-2.jpg\n", 0)
        return ExecResult("", 0)


async def test_render_pdf_uses_fresh_directory_and_returns_every_page():
    session = RecordingSession()

    prepared = await render.prepare_pdf(
        session,
        "/workspace/report.pdf",
        b"pdf-bytes",
        convert_to_pdf=False,
    )
    page_paths = await render.rasterize_pdf(session, prepared)

    assert prepared.pdf_path.endswith("/primary.pdf")
    assert session.files[prepared.source_path] == b"pdf-bytes"
    assert [path.rsplit("/", 1)[1] for path in page_paths] == [
        "page-1.jpg",
        "page-2.jpg",
    ]
    assert session.commands[0].startswith("mkdir -p -- /tmp/surfsense-verify-")
    assert any("pdftoppm -jpeg -r 100" in command for command in session.commands)


async def test_render_office_file_uses_private_profile_and_quotes_paths():
    session = RecordingSession()

    result = await render.prepare_pdf(
        session,
        "/workspace/board's report.docx",
        b"docx-bytes",
        convert_to_pdf=True,
    )

    conversion = next(command for command in session.commands if "soffice" in command)
    assert "-env:UserInstallation=file:///tmp/surfsense-soffice-" in conversion
    assert "--outdir /tmp/surfsense-verify-" in conversion
    assert "/primary.docx" in conversion
    assert result.profile_dir
    assert result.profile_dir not in result.build_dir
    assert result.pdf_path.endswith("/primary.pdf")
    assert session.files[result.source_path] == b"docx-bytes"


async def test_render_failure_is_actionable():
    session = RecordingSession(fail_step="soffice")

    with pytest.raises(
        render.ArtifactRenderError, match=r"converting artifact to PDF failed"
    ) as raised:
        await render.prepare_pdf(
            session,
            "/workspace/report.docx",
            b"docx-bytes",
            convert_to_pdf=True,
        )

    assert "conversion error" not in str(raised.value)
    assert session.commands[-1].startswith("rm -rf -- /tmp/surfsense-verify-")
    assert "/tmp/surfsense-soffice-" in session.commands[-1]
