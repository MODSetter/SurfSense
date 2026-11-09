"""The app's first-party list names each plugin's tools as its server registers them.

Read from each `server.py` rather than served: building a licensed plugin needs the
license server's account, which CI does not hold.
"""

import ast
import json
from pathlib import Path

from host.mounted_plugins import RESERVED, plugin_id

PLUGINS = Path(__file__).resolve().parents[2]
FIRST_PARTY_LIST = (
    PLUGINS.parents[1]
    / "surfsense_local/backend/modules/plugins/lists/first_party/plugins.json"
)


def registered_tools(server: Path) -> list[str]:
    """Each function decorated `@<server>.tool(...)`, by its `name=` or its own name."""
    names = []
    for node in ast.walk(ast.parse(server.read_text())):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            call = decorator if isinstance(decorator, ast.Call) else None
            target = call.func if call else decorator
            if isinstance(target, ast.Attribute) and target.attr == "tool":
                named = [
                    k.value for k in (call.keywords if call else []) if k.arg == "name"
                ]
                names.append(ast.literal_eval(named[0]) if named else node.name)
    return names


def served_tools() -> dict[str, list[str]]:
    folders = [*PLUGINS.iterdir(), *(PLUGINS / "proprietary").iterdir()]
    return {
        plugin_id(folder): registered_tools(folder / "server.py")
        for folder in folders
        if folder.name not in RESERVED and (folder / "server.py").is_file()
    }


def test_each_first_party_entry_lists_its_server_s_tools() -> None:
    """A plugin's page shows the list's tools before connecting; they must be the server's."""
    served = served_tools()
    listed = json.loads(FIRST_PARTY_LIST.read_text())["plugins"]

    for entry in listed:
        assert entry["id"] in served, f"{entry['id']}: no server on the host"
        assert sorted(entry["tools"]) == sorted(served[entry["id"]]), entry["id"]


def test_a_server_s_tools_are_read_from_its_source() -> None:
    """So a missing or extra tool in the list fails the test above."""
    samples = Path(__file__).parent / "sample_plugins"

    assert registered_tools(samples / "notes" / "server.py") == ["search"]
    assert registered_tools(samples / "proprietary" / "paid" / "server.py") == [
        "scrape"
    ]
