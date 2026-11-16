"""Issue bodies as GitHub renders the plugin submission form, and stand-ins for its network edges."""

from typing import Any

from registry_check.submission.server_report import ServerReport
from tests.registry_files import SQUARE_SVG

ANSWERS = {
    "Plugin name": "Acme Docs",
    "MCP server URL": "https://mcp.acme.example/mcp",
    "Publisher": "Acme Inc.",
    "One-line description": "Search and read Acme's public documentation.",
    "About": "Search Acme's docs and read any page in full.",
    "Privacy policy URL": "https://acme.example/privacy",
    "Homepage": "https://acme.example",
    "Icon": "https://acme.example/icon.svg",
    "Who can use it": "Free (a free account is fine)",
    "Tool names": "search_docs\nread_page",
    "A prompt to try": "What do Acme's docs say about rate limits?",
}


def issue_body(**changes: str | None) -> str:
    """The form's markdown; a change of None leaves that answer blank."""
    answers: dict[str, Any] = dict(ANSWERS)
    for label, value in changes.items():
        answers[label.replace("_", " ")] = value
    sections = [
        f"### {label}\n\n{value if value else '_No response_'}"
        for label, value in answers.items()
    ]
    sections.append(
        "### Before you send\n\n- [X] There's no key, token or password in this issue."
    )
    return "\n\n".join(sections) + "\n"


def keyless_server(*tools: str) -> Any:
    async def report(url: str) -> ServerReport:
        return ServerReport(
            auth={"type": "none"},
            hosts=["mcp.acme.example"],
            tools=list(tools or ("read_page", "search_docs")),
        )

    return report


def fetching(content: bytes = SQUARE_SVG) -> Any:
    async def fetch(url: str) -> bytes:
        return content

    return fetch


def signing_in_server(kind: str = "oauth") -> Any:
    """A server that lists nothing before sign-in; OAuth adds its authorization host."""

    async def report(url: str, client_id: str | None = None) -> ServerReport:
        hosts = ["mcp.acme.example"]
        if kind == "oauth":
            hosts.append("auth.acme.example")
        auth = {"type": kind}
        if kind == "oauth" and client_id:
            auth["client_id"] = client_id
        return ServerReport(auth=auth, hosts=hosts, tools=None)

    return report
