"""A page's searchable body: what a reader reads, as Markdown, never its code."""

import pytest

from modules.artifacts.web_pages.page_text import page_text

pytestmark = pytest.mark.unit


def test_headings_become_markdown_headings_and_paragraphs_stay_apart():
    """Headings keep their level; each paragraph is its own block."""
    page = (
        "<!doctype html><html><head><title>Q3</title></head><body>"
        "<h1>Q3 revenue</h1><p>Revenue rose <b>12%</b>.</p>"
        "<h2>By region</h2><p>EMEA led.</p></body></html>"
    )
    assert page_text(page) == (
        "# Q3 revenue\n\nRevenue rose 12%.\n\n## By region\n\nEMEA led."
    )


def test_script_style_template_and_the_title_are_left_out():
    """Code and the tab's title never reach search."""
    page = (
        "<head><title>Tab</title><style>p{color:red}</style></head>"
        "<script>const secret = 1</script><template><p>later</p></template>"
        "<p>Shown</p><noscript>Turn on scripts</noscript>"
    )
    assert page_text(page) == "Shown"


def test_list_items_table_cells_and_alt_text_are_kept():
    """Lists, table rows and alt text are searchable."""
    page = (
        "<ul><li>One</li><li>Two</li></ul>"
        "<table><tr><th>Region</th><th>Sales</th></tr>"
        "<tr><td>EMEA</td><td>4.2</td></tr></table>"
        '<img alt="Revenue by month" src="data:,">'
    )
    assert page_text(page) == (
        "- One\n\n- Two\n\nRegion | Sales\n\nEMEA | 4.2\n\nRevenue by month"
    )


def test_svg_text_is_kept_so_a_chart_label_is_searchable():
    """An inline chart's title and labels are searchable."""
    page = '<svg><title>Chart</title><text x="1">March</text><text>9.1</text></svg>'
    assert page_text(page) == "Chart\n\nMarch 9.1"


def test_whitespace_is_collapsed_and_entities_decoded():
    """Markup whitespace collapses and entities read as characters."""
    assert page_text("<p>  a\n\n  b &amp; c&nbsp;d </p>") == "a b & c d"


def test_a_page_with_no_text_reads_as_empty():
    """A page of code alone has no body."""
    assert page_text("<div><script>x()</script></div>") == ""
