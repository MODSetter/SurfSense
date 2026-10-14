"""A PDF form's fields listed, and filled on a copy, optionally flattened."""

from io import BytesIO

import pypdf
import pypdfium2
import pytest

from modules.pdf_tools.form_fields import form_fields
from modules.pdf_tools.form_fill import fill_form
from modules.pdf_tools.opened_pdf import open_pdf
from modules.pdf_tools.refusal import PdfRefusedError
from tests.unit.pdf_tools.pdfs import (
    drawn_texts,
    form,
    heavy,
    long_choices,
    numbered,
    shared_resources,
    texts,
    xfa_only,
)

pytestmark = pytest.mark.unit


def _values(data: bytes) -> dict[str, object]:
    fields = pypdf.PdfReader(BytesIO(data)).get_fields() or {}
    return {name: field.get("/V") for name, field in fields.items()}


def test_fields_are_listed_with_kind_value_options_and_page() -> None:
    """What the model needs to fill a form without guessing a name or an option."""
    fields = {field.name: field for field in form_fields(open_pdf(form(), "a"))}

    assert list(fields) == ["name", "agree", "country", "size", "notes"]
    assert (fields["name"].kind, fields["name"].pages) == ("text", (1,))
    assert fields["agree"].kind == "checkbox"
    assert fields["agree"].options == ("Yes",)
    assert fields["agree"].value == "Off"
    assert fields["country"].kind == "dropdown"
    assert fields["country"].options == ("India", "Norway")
    assert fields["country"].value == "India"
    assert fields["size"].kind == "radio"
    assert fields["size"].options == ("small", "large")
    assert fields["size"].value == "small"
    assert fields["notes"].pages == (2,)


def test_a_pdf_without_a_form_has_no_fields() -> None:
    """No form is an empty list, not an error."""
    assert form_fields(open_pdf(numbered(1), "a")) == []


def test_an_xfa_only_form_is_refused_as_unsupported() -> None:
    """Its fields are not PDF fields, so pypdf cannot fill them."""
    with pytest.raises(PdfRefusedError, match="XFA"):
        form_fields(open_pdf(xfa_only(), "a"))


def test_filling_sets_each_kind_of_field_on_a_copy() -> None:
    """Each kind takes the value a model naturally gives it; the PDF read stays blank."""
    original = form()
    reader = open_pdf(original, "a")

    filled = fill_form(
        reader,
        {
            "name": "Asha Rao",
            "agree": True,
            "country": "Norway",
            "size": "large",
            "notes": "Arrives Friday",
        },
        flatten=False,
    )

    assert _values(filled.data) == {
        "name": "Asha Rao",
        "agree": "/Yes",
        "country": "Norway",
        "size": "/large",
        "notes": "Arrives Friday",
    }
    assert filled.pages == [1, 2]
    assert _values(original)["name"] == ""


def test_a_flattened_copy_has_the_values_on_the_page_and_no_fields() -> None:
    """A final copy nobody can change: the values are page content."""
    filled = fill_form(
        open_pdf(form(), "a"),
        {"name": "Asha Rao", "notes": "Arrives Friday", "size": "large"},
        flatten=True,
    )

    reader = pypdf.PdfReader(BytesIO(filled.data))
    assert not reader.get_fields()
    assert all(not page.get("/Annots") for page in reader.pages)
    pages = texts(filled.data)
    assert "Asha Rao" in pages[0]
    assert "Arrives Friday" in pages[1]


def test_a_flattened_radio_group_shows_the_button_chosen() -> None:
    """Both buttons of a group share a name; each keeps its own look."""
    filled = fill_form(open_pdf(form(), "a"), {"size": "large"}, flatten=True)

    pdf = pypdfium2.PdfDocument(filled.data)
    try:
        image = pdf[0].render(scale=1).to_pil().convert("L")
    finally:
        pdf.close()
    # Where reportlab draws each button's centre, 15 pt circles at y 640.
    top = image.height - 646
    small, large = image.getpixel((77, top)), image.getpixel((125, top))
    assert large < 100 < small


def test_an_unknown_field_is_refused_naming_the_fields_there_are() -> None:
    """The model corrects a guessed name from the list in the refusal."""
    with pytest.raises(PdfRefusedError) as refused:
        fill_form(open_pdf(form(), "a"), {"surname": "Rao"}, flatten=False)

    assert 'no field "surname"' in str(refused.value)
    assert "name, agree, country, size, notes" in str(refused.value)


def test_a_choice_not_offered_is_refused_naming_the_choices() -> None:
    """A dropdown set to a value it does not offer shows blank in most viewers."""
    with pytest.raises(PdfRefusedError) as refused:
        fill_form(open_pdf(form(), "a"), {"country": "Chile"}, flatten=False)

    assert 'Field "country" takes one of: India, Norway.' in str(refused.value)


def test_a_radio_value_not_offered_is_refused() -> None:
    """A state the group has no appearance for would show nothing chosen."""
    with pytest.raises(PdfRefusedError, match="small, large"):
        fill_form(open_pdf(form(), "a"), {"size": "medium"}, flatten=False)


def test_a_checkbox_takes_true_or_false() -> None:
    """Anything else is a guess at what the user meant."""
    with pytest.raises(PdfRefusedError, match="true or false"):
        fill_form(open_pdf(form(), "a"), {"agree": "maybe"}, flatten=False)


def test_filling_nothing_is_refused() -> None:
    """A copy with nothing filled is a duplicate in Studio."""
    with pytest.raises(PdfRefusedError, match="at least one field"):
        fill_form(open_pdf(form(), "a"), {}, flatten=False)


def test_filling_a_pdf_without_a_form_is_refused() -> None:
    """The refusal points at stamping, which is what such a request needs."""
    with pytest.raises(PdfRefusedError, match="has no form fields"):
        fill_form(open_pdf(numbered(1), "a"), {"name": "x"}, flatten=False)


def test_flattening_pages_that_share_resources_draws_each_pages_own_fields() -> None:
    """Pages often share one resource dictionary; each page still shows its own values."""
    filled = fill_form(
        open_pdf(shared_resources(form()), "a"),
        {"name": "Asha Rao", "notes": "Arrives Friday"},
        flatten=True,
    )

    first, second = texts(filled.data)
    assert "Asha Rao" in first
    assert "Arrives Friday" not in first
    assert "Arrives Friday" in second
    assert "Asha Rao" not in second


def test_a_flattened_copy_keeps_each_pages_own_content_as_stored() -> None:
    """A page's content is never decoded to draw the fields over it."""
    filled = fill_form(
        open_pdf(heavy(form(), 8 * 1024 * 1024), "a"),
        {"name": "Asha Rao", "notes": "Arrives Friday"},
        flatten=True,
    )

    assert len(filled.data) < 1024 * 1024
    first, second = drawn_texts(filled.data)
    assert "Application" in first
    assert "Asha Rao" in first
    assert "Arrives Friday" in second


def test_a_choice_not_offered_names_only_the_first_choices_of_a_long_list() -> None:
    """A refusal stays a sentence, not the whole list."""
    with pytest.raises(PdfRefusedError) as refused:
        fill_form(
            open_pdf(long_choices(1, 2000), "a"), {"field 0": "Atlantis"}, flatten=False
        )

    assert "Choice 0 of field 0" in str(refused.value)
    assert "and 1,950 more" in str(refused.value)
    assert len(str(refused.value)) < 4000
