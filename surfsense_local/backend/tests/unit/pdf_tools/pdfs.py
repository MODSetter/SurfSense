"""PDFs built for the PDF tools' tests: pages that name themselves, forms, locks."""

from io import BytesIO

import pypdf
import pypdfium2
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def numbered(count: int, label: str = "Page", size: tuple[float, float] = A4) -> bytes:
    """`count` pages, each reading "<label> <n>"."""
    out = BytesIO()
    drawing = canvas.Canvas(out, pagesize=size)
    for number in range(1, count + 1):
        drawing.drawString(72, 72, f"{label} {number}")
        drawing.showPage()
    drawing.save()
    return out.getvalue()


def form() -> bytes:
    """A two-page form: a name, a checkbox, a dropdown and a radio group on page 1, notes on page 2."""
    out = BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    fields = drawing.acroForm
    drawing.drawString(72, 800, "Application")
    fields.textfield(name="name", x=120, y=760, width=200, height=20)
    fields.checkbox(name="agree", x=72, y=720, size=15)
    fields.choice(
        name="country",
        options=["India", "Norway"],
        value="India",
        x=72,
        y=680,
        width=120,
        height=20,
    )
    fields.radio(name="size", value="small", selected=True, x=72, y=640, size=15)
    fields.radio(name="size", value="large", selected=False, x=120, y=640, size=15)
    drawing.showPage()
    drawing.drawString(72, 800, "Notes page")
    fields.textfield(name="notes", x=72, y=700, width=200, height=20)
    drawing.showPage()
    drawing.save()
    return out.getvalue()


def long_choices(fields: int, options: int) -> bytes:
    """One page of `fields` dropdowns, each offering `options` long choices."""
    out = BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    for number in range(fields):
        choices = [f"Choice {n} of field {number}, spelled out" for n in range(options)]
        drawing.acroForm.choice(
            name=f"field {number}",
            options=choices,
            value=choices[0],
            x=72,
            y=800 - 12 * number,
            width=120,
            height=10,
        )
    drawing.showPage()
    drawing.save()
    return out.getvalue()


def locked(data: bytes, user_password: str, owner_password: str = "owner") -> bytes:
    """`data` encrypted; an empty user password opens it without asking."""
    writer = pypdf.PdfWriter(clone_from=pypdf.PdfReader(BytesIO(data)))
    writer.encrypt(user_password=user_password, owner_password=owner_password)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def xfa_only() -> bytes:
    """A form whose fields live only in XFA, as LiveCycle Designer saves a dynamic form."""
    writer = pypdf.PdfWriter(clone_from=pypdf.PdfReader(BytesIO(numbered(1))))
    writer._root_object[NameObject("/AcroForm")] = DictionaryObject(
        {
            NameObject("/Fields"): ArrayObject(),
            NameObject("/XFA"): ArrayObject(),
        }
    )
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def heavy(data: bytes, decoded_bytes: int) -> bytes:
    """`data` with every page drawing one shared, compressed content stream of
    `decoded_bytes` first: a few KB on disk that decode to many MB per page."""
    writer = pypdf.PdfWriter(clone_from=pypdf.PdfReader(BytesIO(data)))
    filler = DecodedStreamObject()
    filler.set_data(b"q Q\n" * (decoded_bytes // 4))
    shared = writer._add_object(filler.flate_encode())
    for page in writer.pages:
        own = page.raw_get("/Contents")
        page[NameObject("/Contents")] = ArrayObject([shared, own])
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def shared_resources(data: bytes) -> bytes:
    """`data` with every page using the first page's resource dictionary, as many
    PDF makers write it."""
    writer = pypdf.PdfWriter(clone_from=pypdf.PdfReader(BytesIO(data)))
    shared = writer._add_object(writer.pages[0]["/Resources"])
    for page in writer.pages:
        page[NameObject("/Resources")] = shared
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def texts(data: bytes) -> list[str]:
    """Each page's text, stripped."""
    return [
        page.extract_text().strip() for page in pypdf.PdfReader(BytesIO(data)).pages
    ]


def drawn_texts(data: bytes) -> list[str]:
    """Each page's text as pdfium reads it: fast on content that decodes to MBs."""
    pdf = pypdfium2.PdfDocument(data)
    try:
        return [page.get_textpage().get_text_range() for page in pdf]
    finally:
        pdf.close()
