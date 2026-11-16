"""`live` connects to each new or changed server with the app's own MCP client.

Any MCP server passes that the app could use; what MCP leaves optional only warns.
"""

import json
from pathlib import Path

from registry_check.__main__ import main
from tests.live_servers import (
    SECRET,
    RequiringKey,
    answering_secret,
    authorization_server,
    closed_port,
    docs_server,
    docs_sse_server,
    entry,
    not_mcp,
    oauth_server,
    serving,
)


def live(
    tmp_path: Path,
    plugins: list[dict],
    base: list[dict] | None = None,
) -> int:
    registry = tmp_path / "plugins.json"
    registry.write_text(json.dumps({"schema_version": 1, "plugins": plugins}))
    argv = ["live", "--registry", str(registry)]
    if base is not None:
        base_file = tmp_path / "base.json"
        base_file.write_text(json.dumps({"schema_version": 1, "plugins": base}))
        argv += ["--base", str(base_file)]
    return main(argv)


def test_a_server_that_lists_its_tools_as_the_entry_says_passes(tmp_path, capsys):
    with serving(docs_server()) as url:
        assert live(tmp_path, [entry(f"{url}/mcp")]) == 0
    assert "live check: passed" in capsys.readouterr().err


def test_a_tool_not_listed_without_sign_in_only_warns(tmp_path, capsys):
    # Some servers list more tools once signed in; the maintainer confirms those.
    tools = ["read_page", "search_docs", "delete_page"]
    with serving(docs_server()) as url:
        assert live(tmp_path, [entry(f"{url}/mcp", tools=tools)]) == 0
    assert (
        'plugins[0] "docs": warning: tools: delete_page not listed without sign-in'
        in capsys.readouterr().err
    )


def test_a_tool_the_entry_leaves_out_fails(tmp_path, capsys):
    with serving(docs_server()) as url:
        assert live(tmp_path, [entry(f"{url}/mcp", tools=["search_docs"])]) == 1
    assert "tools: the server also lists read_page" in capsys.readouterr().err


def test_an_entry_listing_no_tools_is_told_them_and_passes(tmp_path, capsys):
    plugin = entry("")
    del plugin["tools"]
    with serving(docs_server()) as url:
        plugin["url"] = f"{url}/mcp"
        assert live(tmp_path, [plugin]) == 0
    assert "warning: tools: not listed; the server lists read_page, search_docs" in (
        capsys.readouterr().err
    )


def test_tools_without_annotations_pass_with_a_warning(tmp_path, capsys):
    with serving(docs_server(annotated=False)) as url:
        assert live(tmp_path, [entry(f"{url}/mcp")]) == 0
    err = capsys.readouterr().err
    assert "warning: read_page: no readOnlyHint or destructiveHint" in err


def test_a_server_that_cannot_be_reached_fails(tmp_path, capsys):
    assert live(tmp_path, [entry(closed_port())]) == 1
    assert "url: could not be reached" in capsys.readouterr().err


def test_a_url_with_no_mcp_server_fails(tmp_path, capsys):
    with serving(not_mcp()) as url:
        assert live(tmp_path, [entry(f"{url}/mcp")]) == 1
    assert "url: does not answer MCP over Streamable HTTP" in (capsys.readouterr().err)


def test_a_server_asking_for_sign_in_fails_when_auth_is_none(tmp_path, capsys):
    with serving(RequiringKey(docs_server())) as url:
        assert live(tmp_path, [entry(f"{url}/mcp")]) == 1
    assert "auth: none, but the server asks for sign-in (401)" in (
        capsys.readouterr().err
    )


def test_a_server_that_takes_a_key_passes_without_one(tmp_path):
    token = {"type": "token", "title": "API key", "description": "From Docs."}
    with serving(RequiringKey(docs_server())) as url:
        assert live(tmp_path, [entry(f"{url}/mcp", auth=token)]) == 0


def test_a_key_server_that_answers_without_a_key_warns(tmp_path, capsys):
    token = {"type": "token", "title": "API key", "description": "From Docs."}
    with serving(docs_server()) as url:
        assert live(tmp_path, [entry(f"{url}/mcp", auth=token)]) == 0
    assert "warning: auth: token, but the server listed its tools without a key" in (
        capsys.readouterr().err
    )


def test_an_oauth_server_whose_hosts_are_listed_passes(tmp_path):
    with (
        serving(authorization_server()) as issuer,
        serving(oauth_server(issuer)) as url,
    ):
        plugin = entry(f"{url}/mcp", auth={"type": "oauth"})
        assert live(tmp_path, [plugin]) == 0


def test_an_oauth_server_signing_in_on_an_unlisted_host_fails(tmp_path, capsys):
    with (
        serving(authorization_server()) as issuer,
        serving(oauth_server(issuer)) as url,
    ):
        plugin = entry(f"{url}/mcp", auth={"type": "oauth"}, hosts=["mcp.docs.example"])
        assert live(tmp_path, [plugin]) == 1
    assert "hosts: sign-in reaches 127.0.0.1, which hosts leaves out" in (
        capsys.readouterr().err
    )


def test_an_oauth_server_naming_no_authorization_server_fails(tmp_path, capsys):
    with serving(oauth_server(None)) as url:
        plugin = entry(f"{url}/mcp", auth={"type": "oauth"})
        assert live(tmp_path, [plugin]) == 1
    assert "auth: oauth, but the server names no authorization server" in (
        capsys.readouterr().err
    )


def test_an_oauth_server_surfsense_cannot_register_with_fails(tmp_path, capsys):
    with (
        serving(authorization_server(registration=False)) as issuer,
        serving(oauth_server(issuer)) as url,
    ):
        plugin = entry(f"{url}/mcp", auth={"type": "oauth"})
        assert live(tmp_path, [plugin]) == 1
    assert "auth: the authorization server takes neither" in capsys.readouterr().err


def test_a_client_registered_in_advance_needs_no_registration(tmp_path):
    with (
        serving(authorization_server(registration=False)) as issuer,
        serving(oauth_server(issuer)) as url,
    ):
        plugin = entry(f"{url}/mcp", auth={"type": "oauth", "client_id": "surfsense"})
        assert live(tmp_path, [plugin]) == 0


def test_a_client_metadata_document_is_enough_to_register(tmp_path):
    with (
        serving(
            authorization_server(registration=False, metadata_document=True)
        ) as issuer,
        serving(oauth_server(issuer)) as url,
    ):
        assert live(tmp_path, [entry(f"{url}/mcp", auth={"type": "oauth"})]) == 0


def test_only_new_or_changed_entries_are_contacted(tmp_path):
    unchanged = entry(closed_port(), id="old")
    with serving(docs_server()) as url:
        added = entry(f"{url}/mcp")
        assert live(tmp_path, [unchanged, added], base=[unchanged]) == 0


def test_what_a_server_answers_never_reaches_the_log(tmp_path, capfd):
    """A pull request's log is public: a reason is reported, never the answer itself."""
    with serving(answering_secret()) as url:
        assert live(tmp_path, [entry(f"{url}/mcp")]) == 1
    out, err = capfd.readouterr()
    assert "url: does not answer MCP over Streamable HTTP" in err
    assert SECRET not in out + err


def test_a_key_server_refusing_with_another_code_only_warns(tmp_path, capsys):
    with serving(not_mcp()) as url:
        listed = entry(
            f"{url}/mcp",
            auth={"type": "token", "title": "Key", "description": "From Docs."},
        )
        assert live(tmp_path, [listed]) == 0
    assert "answered 404 without a key" in capsys.readouterr().err


def test_a_server_on_the_older_sse_transport_alone_fails(tmp_path, capsys):
    """Neither of SurfSense's engines speaks SSE, so its users could never call it."""
    with serving(docs_sse_server()) as url:
        assert live(tmp_path, [entry(f"{url}/sse")]) == 1
    assert "does not answer MCP over Streamable HTTP" in capsys.readouterr().err


def test_a_headers_entry_is_expected_to_refuse_without_its_key(tmp_path):
    """As a token entry is: CI holds no key, so a refusal is what a keyed server says."""
    headers = {"type": "headers", "headers": [{"name": "x-api-key"}]}
    with serving(RequiringKey(docs_server())) as url:
        assert live(tmp_path, [entry(f"{url}/mcp", auth=headers)]) == 0


def test_an_oauth_entry_for_the_users_own_app_needs_no_registration(tmp_path):
    """Its users bring a registered app, so a provider without registration is fine."""
    with (
        serving(authorization_server(registration=False)) as issuer,
        serving(oauth_server(issuer)) as url,
    ):
        listed = entry(
            f"{url}/mcp",
            auth={"type": "oauth", "user_client": True},
            hosts=["127.0.0.1"],
        )
        assert live(tmp_path, [listed]) == 0
