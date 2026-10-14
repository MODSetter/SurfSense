"""The offline check a registry pull request must pass, one rule per test."""

from pathlib import Path

import pytest

from registry_check.static.checked_list import problems_in
from tests.registry_files import valid_entry, write_registry


def problems(tmp_path: Path, plugins, **kwargs) -> list[str]:
    registry, first_party = write_registry(tmp_path, plugins, **kwargs)
    return problems_in(registry, first_party)


def test_a_valid_entry_has_no_problems(tmp_path):
    assert problems(tmp_path, [valid_entry()]) == []


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"id": "Acme"}, "id"),
        ({"id": "-acme"}, "id"),
        ({"id": "a" * 65}, "id"),
        ({"kind": "bundle"}, "kind"),
        ({"verification": "unreviewed"}, "verification"),
        ({"verification": "verified"}, "domain"),
        ({"verification": "verified", "domain": "vercel.app"}, "domain"),
        ({"verification": "verified", "domain": "mcp.acme.example"}, "domain"),
        ({"verification": "verified", "domain": "other.example"}, "domain"),
        ({"auth": {"type": "license"}}, "auth"),
        ({"auth": {"type": "oauth", "client_secret": "x"}}, "auth"),
        ({"access": "license"}, "access"),
        ({"access": "external"}, "access_note"),
        ({"privacy_policy": None}, "privacy_policy"),
        ({"url": "http://mcp.acme.example/mcp"}, "url"),
        ({"url": "https://me:pw@mcp.acme.example/mcp"}, "url"),
        ({"hosts": ["other.example"]}, "hosts"),
        (
            {"url": "https://localhost/mcp", "hosts": ["localhost"]},
            "hosts",
        ),
        ({"hosts": ["mcp.acme.example", "127.0.0.1"]}, "hosts"),
        ({"name": ""}, "name"),
        ({"name": "n" * 81}, "name"),
        ({"description": "d" * 201}, "description"),
        ({"author": "a" * 81}, "author"),
        ({"min_app_version": "2.3"}, "min_app_version"),
        ({"homepage": "javascript:alert(1)"}, "homepage"),
        ({"about": ""}, "about"),
        ({"about": "a" * 601}, "about"),
        ({"tools": "search"}, "tools"),
        ({"tools": [{"name": "search"}]}, "tools"),
        ({"tools": ["has space"]}, "tools"),
        ({"tools": [""]}, "tools"),
        ({"tools": ["search", "search"]}, "tools"),
        ({"added": "2026-13"}, "added"),
        ({"added": "October 2026"}, "added"),
        ({"added": "2026-10-12"}, "added"),
    ],
)
def test_a_broken_field_is_named(tmp_path, overrides, field):
    found = problems(tmp_path, [valid_entry(**overrides)])
    assert len(found) == 1, found
    assert found[0].startswith("plugins[0] ")
    assert f"{field}:" in found[0]


def test_optional_and_unknown_fields_are_allowed(tmp_path):
    entry = valid_entry(
        min_app_version="2.3.0",
        homepage="https://acme.example",
        about="Search everything Acme holds, and read it whole.",
        tools=["search", "fetch"],
        added="2026-10",
        future_field={"anything": True},
        auth={"type": "oauth", "client_id": "abc", "scopes": ["read"]},
    )
    assert problems(tmp_path, [entry]) == []


def test_a_token_entry_names_what_to_paste(tmp_path):
    found = problems(tmp_path, [valid_entry(auth={"type": "token"})])
    assert len(found) == 1
    assert "auth:" in found[0]


def test_ids_are_unique_within_the_registry(tmp_path):
    found = problems(tmp_path, [valid_entry(), valid_entry()])
    assert found == ['plugins[1] "acme": id: listed twice']


def test_ids_are_unique_across_the_first_party_list(tmp_path):
    found = problems(
        tmp_path, [valid_entry(id="reddit")], first_party=[{"id": "reddit"}]
    )
    assert found == ['plugins[0] "reddit": id: already used by the first-party list']


def test_a_removed_id_is_never_listed_again(tmp_path):
    found = problems(
        tmp_path, [valid_entry()], removed=[{"id": "acme", "reason": "Shut down."}]
    )
    assert found == ['plugins[0] "acme": id: removed, and an id is never reused']


def test_a_removed_entry_gives_a_reason(tmp_path):
    found = problems(tmp_path, [], removed=[{"id": "old"}])
    assert found == ['removed[0] "old": reason: required']


def test_the_list_itself_must_have_the_known_shape(tmp_path):
    registry = tmp_path / "plugins.json"
    registry.write_text('{"schema_version": 2, "plugins": []}')
    _, first_party = write_registry(tmp_path / "fp", [])
    found = problems_in(registry, first_party)
    assert "schema_version: must be 1" in found


def test_a_verified_entry_s_server_is_on_its_proven_domain(tmp_path):
    """The server, which receives every call, is on the domain whose ownership was proven."""
    entry = valid_entry(verification="verified", domain="acme.example")

    assert problems(tmp_path, [entry]) == []


def test_a_verified_oauth_entry_may_sign_in_elsewhere(tmp_path):
    """A sign-in host sees the sign-in, never a call, so it may be off the domain."""
    oauth = valid_entry(
        verification="verified",
        domain="acme.example",
        auth={"type": "oauth"},
        hosts=["mcp.acme.example", "accounts.google.com"],
    )
    keyless = valid_entry(
        verification="verified",
        domain="acme.example",
        hosts=["mcp.acme.example", "collector.example"],
    )

    assert problems(tmp_path, [oauth]) == []
    found = problems(tmp_path / "keyless", [keyless])
    assert len(found) == 1 and "domain:" in found[0], found
