from __future__ import annotations

import pytest

from app.artifacts.verification import service
from app.artifacts.verification.formats.html import check_html
from app.artifacts.verification.formats.registry import HTML_MIME, get_format_adapter
from app.artifacts.verification.receipt import read_receipt, receipt_path
from tests.utils.fake_sandbox import FakeSandboxSession

SECRET = "test-secret"
WORKSPACE_ID = 7


def test_clean_html_fragment_and_registry():
    result = check_html(
        b"<style>button{color:red}</style><button>Calculate</button>"
        b"<script>document.querySelector('button').onclick=()=>{}</script>"
    )
    adapter = get_format_adapter("/workspace/calculator.html")

    assert result.clean
    assert result.notes == ()
    assert adapter.name == "html"
    assert adapter.mime_type == HTML_MIME
    assert not adapter.requires_visual_review
    assert not adapter.convert_to_pdf


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (b" \n\t", "empty"),
        (b"\xff", "UTF-8"),
        (b"plain text", "no markup"),
        (b"<!doctype html><div>content</div>", "fragment"),
        (b"<html><div>content</div></html>", "fragment"),
        (b"<div>content</div></body>", "fragment"),
    ],
)
def test_html_structural_findings(data, message):
    result = check_html(data)

    assert not result.clean
    assert any(message in finding for finding in result.findings)


def test_external_resources_are_advisory_and_google_fonts_are_allowed():
    result = check_html(
        b'<link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet">'
        b'<script src="https://example.com/app.js"></script>'
        b'<div style="background:url(https://example.com/pixel.png)">Ready</div>'
    )

    assert result.clean
    assert len(result.notes) == 2
    assert all("will be blocked" in note for note in result.notes)
    assert not any("fonts.googleapis.com" in note for note in result.notes)


async def test_verify_html_skips_render_and_vision():
    path = "/workspace/calculator.html"
    session = FakeSandboxSession({path: b"<button>Calculate</button>"})

    result = await service.verify_artifact(
        session,
        path,
        workspace_id=WORKSPACE_ID,
        vision_llm=object(),
        secret_key=SECRET,
    )
    receipt = await read_receipt(
        session,
        SECRET,
        workspace_id=WORKSPACE_ID,
        primary_path=path,
    )

    assert result.verified
    assert result.preview_path is None
    assert receipt.format == "html"
    assert receipt.visual == "not_required"
    assert receipt.preview_path is None
    assert receipt.preview_sha256 is None
    assert not any(
        "soffice" in command or "pdftoppm" in command for command in session.commands
    )


async def test_verify_invalid_html_issues_no_receipt():
    path = "/workspace/calculator.html"
    session = FakeSandboxSession({path: b"<html><button>Calculate</button></html>"})

    result = await service.verify_artifact(
        session,
        path,
        workspace_id=WORKSPACE_ID,
        vision_llm=None,
        secret_key=SECRET,
    )

    assert not result.verified
    assert any("fragment" in finding for finding in result.findings)
    assert session.files[receipt_path(path)] == b""
