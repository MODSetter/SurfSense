from __future__ import annotations

from types import ModuleType, SimpleNamespace


def _load_check_pdf():
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[4]
        / "docker/sandbox/skills/pdf/scripts/check_pdf.py"
    )
    module = ModuleType("surfsense_check_pdf")
    exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    return module


class FakePage:
    def __init__(
        self,
        *,
        text: str = "A sufficiently long line of document text.",
        x: float = 100,
        y: float = 100,
        embedded: bool = True,
    ) -> None:
        self.text = text
        self.x = x
        self.y = y
        self.mediabox = SimpleNamespace(left=0, right=612, bottom=0, top=792)
        descriptor = {"/FontFile2": object()} if embedded else {}
        self.resources = {
            "/Font": {"/F1": {"/FontDescriptor": descriptor}}
        }

    def get(self, key, default=None):
        return self.resources if key == "/Resources" else default

    def extract_text(self, visitor_text=None):
        if visitor_text:
            visitor_text(
                self.text,
                [1, 0, 0, 1, 0, 0],
                [1, 0, 0, 1, self.x, self.y],
                None,
                12,
            )
        return self.text


def test_pdf_checks_detect_margin_and_unembedded_font():
    check_pdf = _load_check_pdf()
    page = FakePage(x=10, embedded=False)

    assert check_pdf._text_margin_violations(page, 50)
    assert check_pdf._page_unembedded_fonts(page) == ["/F1"]


def test_pdf_check_reports_near_blank_page(monkeypatch, tmp_path, capsys):
    check_pdf = _load_check_pdf()
    pdf = tmp_path / "out.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(
        check_pdf,
        "parse_args",
        lambda: SimpleNamespace(
            path=pdf, expect_pages=None, margin_pt=50, min_chars=20
        ),
    )
    monkeypatch.setattr(
        check_pdf, "PdfReader", lambda _path: SimpleNamespace(pages=[FakePage(text="x")])
    )

    try:
        check_pdf.main()
    except SystemExit as exc:
        assert "near-blank" in str(exc)
    else:
        raise AssertionError("near-blank PDF passed verification")
    assert capsys.readouterr().out == ""


def test_pdf_check_emits_verification_sentinel(monkeypatch, tmp_path, capsys):
    check_pdf = _load_check_pdf()
    pdf = tmp_path / "out.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(
        check_pdf,
        "parse_args",
        lambda: SimpleNamespace(
            path=pdf, expect_pages=1, margin_pt=50, min_chars=20
        ),
    )
    monkeypatch.setattr(
        check_pdf, "PdfReader", lambda _path: SimpleNamespace(pages=[FakePage()])
    )

    check_pdf.main()

    assert f"SURFSENSE_VERIFIED: {pdf}" in capsys.readouterr().out
