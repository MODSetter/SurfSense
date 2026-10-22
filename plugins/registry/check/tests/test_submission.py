"""A plugin submission issue becomes a registry entry, or a list of what to fix, field by field."""

import datetime

from registry_check.submission.submission_check import check_submission
from tests.registry_files import SQUARE_SVG, valid_entry, write_registry
from tests.submission_forms import (
    fetching,
    issue_body,
    keyless_server,
    signing_in_server,
)


def check(tmp_path, body, server=None, fetch=None, plugins=None):
    registry, first_party = write_registry(tmp_path, plugins or [])
    return check_submission(
        body,
        registry,
        first_party,
        report_server=server or keyless_server(),
        fetch_icon=fetch or fetching(),
    )


def test_a_keyless_server_becomes_a_community_entry_with_the_tools_it_lists(
    tmp_path,
):
    found = check(tmp_path, issue_body())
    assert found.problems == []
    assert found.entry == {
        "id": "acme-docs",
        "kind": "remote",
        "verification": "community",
        "name": "Acme Docs",
        "description": "Search and read Acme's public documentation.",
        "author": "Acme Inc.",
        "url": "https://mcp.acme.example/mcp",
        "auth": {"type": "none"},
        "hosts": ["mcp.acme.example"],
        "access": "free",
        "privacy_policy": "https://acme.example/privacy",
        "homepage": "https://acme.example",
        "icon": "acme-docs.svg",
        "tools": ["search_docs", "read_page"],
        "added": datetime.datetime.now(datetime.UTC).strftime("%Y-%m"),
        "about": "Search Acme's docs and read any page in full.",
    }


def test_a_blank_required_answer_is_named_by_its_question(tmp_path):
    found = check(tmp_path, issue_body(Privacy_policy_URL=None))
    assert "Privacy policy URL: required" in found.problems
    assert found.entry is None


def test_a_name_another_plugin_holds_is_refused(tmp_path):
    found = check(tmp_path, issue_body(), plugins=[valid_entry(id="acme-docs")])
    assert any(p.startswith("Plugin name: ") for p in found.problems)


def test_tool_names_are_required_since_the_page_shows_them(tmp_path):
    found = check(tmp_path, issue_body(Tool_names=None))
    assert "Tool names: required" in found.problems


def test_a_tool_the_server_lists_but_the_form_leaves_out_is_refused(tmp_path):
    found = check(tmp_path, issue_body(Tool_names="search_docs"))
    assert found.entry is None
    assert found.problems == [
        "Tool names: your server also lists read_page; add it. "
        "It lists: read_page, search_docs"
    ]


def test_a_tool_not_listed_without_sign_in_is_left_to_review(tmp_path):
    body = issue_body(Tool_names="search_docs\nread_page\ndelete_page")
    found = check(tmp_path, body)
    assert found.problems == []
    assert found.entry["tools"] == ["search_docs", "read_page", "delete_page"]
    assert any("delete_page" in w for w in found.warnings)


def test_a_server_behind_sign_in_takes_its_tools_as_declared(tmp_path):
    found = check(tmp_path, issue_body(), server=signing_in_server("oauth"))
    assert found.problems == []
    assert found.entry["tools"] == ["search_docs", "read_page"]
    assert any(w.startswith("Tool names: ") for w in found.warnings)


def test_a_server_taking_a_key_asks_the_submitter_nothing_about_it(tmp_path):
    found = check(tmp_path, issue_body(), server=signing_in_server("token"))
    assert found.problems == []
    assert found.entry["auth"] == {"type": "token"}
    assert not any(w.startswith("Key") for w in found.warnings)


def test_a_paid_plugin_says_what_users_must_buy(tmp_path):
    paid = "Paid: users need a plan or subscription you sell"
    found = check(tmp_path, issue_body(Who_can_use_it=paid))
    assert any(p.startswith("What users must buy or have: ") for p in found.problems)

    noted = issue_body(
        Who_can_use_it=paid, What_users_must_buy_or_have="An Acme Pro plan."
    )
    found = check(tmp_path, noted)
    assert found.entry["access"] == "external"
    assert found.entry["access_note"] == "An Acme Pro plan."


def test_an_icon_breaking_the_icon_rules_is_refused_by_the_icon_question(tmp_path):
    scripted = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><script/></svg>'
    )
    found = check(tmp_path, issue_body(), fetch=fetching(scripted))
    assert "Icon: must not contain <script>" in found.problems


def test_an_icon_dropped_into_the_form_is_read_from_its_markdown(tmp_path):
    asked: list[str] = []

    async def fetch(url: str) -> bytes:
        asked.append(url)
        return SQUARE_SVG

    dropped = "![acme](https://github.com/user-attachments/assets/1234abcd)"
    found = check(tmp_path, issue_body(Icon=dropped), fetch=fetch)
    assert asked == ["https://github.com/user-attachments/assets/1234abcd"]
    assert found.entry["icon"] == "acme-docs.svg"


def test_without_the_box_ticked_nothing_is_contacted(tmp_path):
    body = issue_body().replace("- [X] There's no key", "- [ ] There's no key")

    async def never(url: str):
        raise AssertionError("contacted")

    found = check(tmp_path, body, server=never)
    assert found.problems == ["Before you send: tick the box"]


def test_a_server_address_the_runner_must_not_reach_is_never_contacted(tmp_path):
    async def never(url: str):
        raise AssertionError("contacted")

    body = issue_body(MCP_server_URL="https://169.254.169.254/mcp")
    found = check(tmp_path, body, server=never)
    assert found.problems == ["MCP server URL: must be on a public host"]


def test_a_sign_in_taking_only_registered_apps_lists_it_for_users_own(tmp_path):
    """Not a problem for the publisher: each user brings their own app when connecting."""

    async def registered_only(url: str):
        from registry_check.submission.server_report import ServerReport

        return ServerReport(
            {"type": "oauth", "user_client": True}, ["mcp.acme.example"], None
        )

    found = check(tmp_path, issue_body(), server=registered_only)
    assert found.problems == []
    assert found.entry["auth"] == {"type": "oauth", "user_client": True}
    assert any("own" in w for w in found.warnings)


def test_a_submitted_entry_names_no_transport(tmp_path):
    """Streamable HTTP is the only one SurfSense speaks, so there is none to name."""
    found = check(tmp_path, issue_body())
    assert found.problems == []
    assert "transport" not in found.entry
