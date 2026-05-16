"""Generate deterministic one-page PDFs for connector E2E fixtures."""

from __future__ import annotations

from pathlib import Path

PDF_FIXTURES = {
    "drive-canary.pdf": (
        "Native Drive PDF Canary",
        "This one-page text-layer PDF proves native Drive Docling coverage.",
        "SURFSENSE_E2E_CANARY_TOKEN_DRIVE_PDF_001",
    ),
    "onedrive-canary.pdf": (
        "OneDrive PDF Canary",
        "This one-page text-layer PDF proves OneDrive Docling coverage.",
        "SURFSENSE_E2E_CANARY_TOKEN_ONEDRIVE_PDF_001",
    ),
    "dropbox-canary.pdf": (
        "Dropbox PDF Canary",
        "This one-page text-layer PDF proves Dropbox Docling coverage.",
        "SURFSENSE_E2E_CANARY_TOKEN_DROPBOX_PDF_001",
    ),
    "composio-drive-canary.pdf": (
        "Composio Drive PDF Canary",
        "This one-page text-layer PDF proves Composio Drive Docling coverage.",
        "SURFSENSE_E2E_CANARY_TOKEN_COMPOSIO_DRIVE_PDF_001",
    ),
}


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(lines: tuple[str, str, str]) -> bytes:
    text_ops = ["BT", "/F1 12 Tf", "72 760 Td"]
    for index, line in enumerate(lines):
        if index:
            text_ops.append("0 -18 Td")
        text_ops.append(f"({_escape_pdf_text(line)}) Tj")
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("ascii")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj_number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{obj_number} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def main() -> None:
    out_dir = Path(__file__).parent
    for filename, lines in PDF_FIXTURES.items():
        (out_dir / filename).write_bytes(_build_pdf(lines))


if __name__ == "__main__":
    main()
