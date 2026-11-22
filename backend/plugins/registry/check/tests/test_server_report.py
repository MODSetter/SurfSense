"""What a submitted server says about itself, read from real MCP servers on loopback."""

import anyio

from registry_check.submission.server_report import report_server
from tests.live_servers import (
    RequiringKey,
    authorization_server,
    closed_port,
    docs_server,
    docs_sse_server,
    not_mcp,
    oauth_server,
    serving,
)


def report(url: str):
    return anyio.run(report_server, url)


def test_a_server_listing_its_tools_without_a_key_needs_no_sign_in():
    with serving(docs_server()) as url:
        found = report(f"{url}/mcp")
    assert found.auth == {"type": "none"}
    assert found.hosts == ["127.0.0.1"]
    assert found.tools == ["read_page", "search_docs"]
    assert found.problems == []


def test_a_server_refusing_without_a_key_and_naming_no_sign_in_takes_a_key():
    with serving(RequiringKey(docs_server())) as url:
        found = report(f"{url}/mcp")
    assert found.auth == {"type": "token"}
    assert found.tools is None
    assert found.problems == []


def test_a_server_naming_an_authorization_server_signs_in_with_oauth():
    with (
        serving(authorization_server()) as issuer,
        serving(oauth_server(issuer)) as url,
    ):
        found = report(f"{url}/mcp")
    assert found.auth == {"type": "oauth"}
    assert found.tools is None
    assert found.problems == []


def test_an_oauth_server_taking_only_registered_apps_asks_for_the_users_own():
    """Not a problem: the app asks each user for their own app when they connect."""
    with (
        serving(authorization_server(registration=False)) as issuer,
        serving(oauth_server(issuer)) as url,
    ):
        found = report(f"{url}/mcp")
    assert found.auth == {"type": "oauth", "user_client": True}
    assert found.problems == []


def test_a_server_on_the_older_sse_transport_is_refused_as_one():
    """Told what to give instead, rather than that it is no MCP server."""
    with serving(docs_sse_server()) as url:
        found = report(f"{url}/sse")
    assert found.problems == [
        "is an address on the older HTTP+SSE transport, which SurfSense does not "
        "speak. Give its Streamable HTTP address, which often ends in /mcp"
    ]


def test_an_sse_address_asking_for_sign_in_is_named_and_its_mcp_given():
    """Its 401 would read as a key to take: reviewers are told it is SSE, and where MCP is."""
    with serving(RequiringKey(docs_server())) as url:
        found = report(f"{url}/sse")
    assert found.problems == [
        "is an address on the older HTTP+SSE transport, which SurfSense does not "
        f"speak. Its server answers MCP at {url}/mcp: submit that address"
    ]


def test_an_sse_address_with_nothing_at_its_mcp_is_named():
    with serving(not_mcp()) as url:
        found = report(f"{url}/sse")
    assert found.problems == [
        "is an address on the older HTTP+SSE transport, which SurfSense does not "
        "speak. Give its Streamable HTTP address, which often ends in /mcp"
    ]


def test_a_server_nothing_answers_on_is_a_problem():
    found = report(closed_port())
    assert found.problems == ["could not be reached: the connection failed"]


def test_a_server_refusing_with_another_code_is_asked_to_check_its_url():
    with serving(not_mcp()) as url:
        found = report(f"{url}/mcp")
    assert found.problems == [
        "does not answer MCP over Streamable HTTP: it answered 404. Check it is "
        "your MCP endpoint"
    ]
