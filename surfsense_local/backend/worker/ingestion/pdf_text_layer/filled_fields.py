"""Whether a PDF form holds answers: they live in its fields, which the text layer
never shows, while Docling reads them off the page.

A form dictionary alone is not enough: 11 of the 19 Boston budget PDFs carry one
with no field filled in.
"""

import ctypes
from typing import Any

import pypdfium2.raw as pdfium_c

_CHECKED_KINDS = (pdfium_c.FPDF_FORMFIELD_CHECKBOX, pdfium_c.FPDF_FORMFIELD_RADIOBUTTON)
_TEXT_KINDS = (
    pdfium_c.FPDF_FORMFIELD_TEXTFIELD,
    pdfium_c.FPDF_FORMFIELD_COMBOBOX,
    pdfium_c.FPDF_FORMFIELD_LISTBOX,
)


def holds_filled_fields(pdf: Any) -> bool:
    """Call before any page is loaded, as init_forms asks. Hold shared.pdfium.lock."""
    if pdf.get_formtype() == pdfium_c.FORMTYPE_NONE:
        return False
    pdf.init_forms()
    form = pdf.formenv.raw
    for index in range(len(pdf)):
        page = pdf[index]
        try:
            if any(_filled(form, page, n) for n in range(_annotations(page))):
                return True
        finally:
            page.close()
    return False


def _annotations(page: Any) -> int:
    return max(0, pdfium_c.FPDFPage_GetAnnotCount(page.raw))


def _filled(form: Any, page: Any, n: int) -> bool:
    annotation = pdfium_c.FPDFPage_GetAnnot(page.raw, n)
    if not annotation:
        return False
    try:
        if pdfium_c.FPDFAnnot_GetSubtype(annotation) != pdfium_c.FPDF_ANNOT_WIDGET:
            return False
        kind = pdfium_c.FPDFAnnot_GetFormFieldType(form, annotation)
        # An unticked box reports its value as "Off"; whether it is ticked is the answer.
        if kind in _CHECKED_KINDS:
            return bool(pdfium_c.FPDFAnnot_IsChecked(form, annotation))
        if kind in _TEXT_KINDS:
            return bool(_value(form, annotation).strip())
        return False  # a push button or a signature holds no text
    finally:
        pdfium_c.FPDFPage_CloseAnnot(annotation)


def _value(form: Any, annotation: Any) -> str:
    size = pdfium_c.FPDFAnnot_GetFormFieldValue(form, annotation, None, 0)
    if size <= 2:  # UTF-16 with its terminator: two bytes is an empty value
        return ""
    buffer = ctypes.create_string_buffer(size)
    pdfium_c.FPDFAnnot_GetFormFieldValue(
        form, annotation, ctypes.cast(buffer, ctypes.POINTER(pdfium_c.FPDF_WCHAR)), size
    )
    return buffer.raw[: size - 2].decode("utf-16-le", errors="ignore")
