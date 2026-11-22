"""What a page would load from elsewhere, named so the agent can inline it."""

import pytest

from modules.artifacts.web_pages.outside_resources import outside_resources

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "css",
    [
        '@import url("https://fonts.googleapis.com/css");',
        "@import url('https://fonts.googleapis.com/css');",
        "@import url(https://fonts.googleapis.com/css);",
        '@import "https://fonts.googleapis.com/css";',
        "@import url( https://fonts.googleapis.com/css );",
    ],
)
def test_every_form_of_import_names_the_address(css: str) -> None:
    """Google Fonts' usual import names its address, never `url(`."""
    assert outside_resources(f"<style>{css}</style>") == [
        "https://fonts.googleapis.com/css"
    ]


def test_url_in_a_style_block_and_a_style_attribute_are_named() -> None:
    """A background image loads as much as an <img>."""
    page = (
        "<style>body { background: url('https://cdn.example/bg.png') }</style>"
        '<div style="background-image: url(https://cdn.example/tile.png)"></div>'
    )
    assert outside_resources(page) == [
        "https://cdn.example/bg.png",
        "https://cdn.example/tile.png",
    ]


def test_loading_attributes_are_named_and_links_are_not() -> None:
    """A link is the reader's to follow; src, href on a stylesheet and srcset load."""
    page = (
        '<link rel="stylesheet" href="https://cdn.example/a.css">'
        '<img src="https://cdn.example/b.png" srcset="https://cdn.example/c.png 2x">'
        '<a href="https://surfsense.com">Site</a>'
    )
    assert outside_resources(page) == [
        "https://cdn.example/a.css",
        "https://cdn.example/b.png",
        "https://cdn.example/c.png",
    ]


def test_inline_data_and_fragments_load_nothing() -> None:
    """What the page carries itself is not listed."""
    page = (
        '<img src="data:image/png;base64,iVBORw0KGgo=">'
        "<style>i { background: url(data:image/svg+xml,%3Csvg%3E) }</style>"
        '<use href="#gear"/>'
    )
    assert outside_resources(page) == []


def test_each_address_is_named_once() -> None:
    """The same address used twice is one thing to inline."""
    page = '<img src="https://cdn.example/x.png"><img src="https://cdn.example/x.png">'
    assert outside_resources(page) == ["https://cdn.example/x.png"]
