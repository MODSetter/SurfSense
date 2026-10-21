"""A stored page carries a CSP that leaves it no network, ahead of anything the page wrote."""

import pytest

from modules.artifacts.web_pages.no_network import NO_NETWORK_POLICY, without_network

pytestmark = pytest.mark.unit

META = f'<meta http-equiv="Content-Security-Policy" content="{NO_NETWORK_POLICY}">'


def test_the_policy_allows_no_request():
    """Every request falls to default-src 'none'; only inline code and data URLs load."""
    directives = dict(
        part.strip().split(" ", 1) for part in NO_NETWORK_POLICY.split(";")
    )
    assert directives["default-src"] == "'none'"
    assert directives["script-src"] == "'unsafe-inline'"
    assert directives["img-src"] == "data: blob:"
    assert "connect-src" not in directives  # falls back to default-src 'none'
    assert directives["form-action"] == "'none'"
    assert directives["base-uri"] == "'none'"


def test_it_goes_right_after_the_doctype():
    """The meta follows the doctype, so standards mode is kept."""
    page = "<!DOCTYPE html>\n<html><head><title>T</title></head><body>x</body></html>"
    assert without_network(page) == (
        "<!DOCTYPE html>" + META + "\n<html><head><title>T</title></head>"
        "<body>x</body></html>"
    )


def test_it_comes_before_a_script_placed_ahead_of_the_head():
    """A script written before the head still runs under the policy."""
    page = "<!doctype html><script>fetch('https://x')</script><head></head>"
    held = without_network(page)
    assert held.index(META) < held.index("<script>")


def test_a_page_without_a_doctype_starts_with_it():
    """A fragment gets the meta as its first element."""
    assert without_network("<p>hi</p>") == META + "<p>hi</p>"


def test_comments_and_a_byte_order_mark_before_the_doctype_stay_first():
    """What may precede a doctype stays ahead of it."""
    page = "\ufeff<!-- made by the agent -->\n<!doctype html><p>x</p>"
    assert without_network(page) == (
        "\ufeff<!-- made by the agent -->\n<!doctype html>" + META + "<p>x</p>"
    )


def test_a_doctype_later_in_the_page_is_not_mistaken_for_the_first():
    """Only a leading doctype moves the meta."""
    page = "<p>see <code>&lt;!doctype html&gt;</code></p><!doctype html>"
    assert without_network(page).startswith(META)
