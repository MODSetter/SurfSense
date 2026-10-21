"""The figure kit written into a page where it asks for it, so the model never copies it.

A page names a kit as `<script data-kit="fig"></script>`; the stored page holds
the kit's code there, and stays self-contained under its no-network policy.
"""

import re
from functools import cache

from modules.agent.opencode_config import skills_folder
from modules.agent.tool_endpoint.tool import ToolCallError

# In the skill's folder, where the agent reads it too (skills/surfsense-html/kit/).
KITS = {"fig": "fig.js"}
_ASKED = re.compile(
    r"""<script\b[^>]*?\bdata-kit\s*=\s*["']?([\w-]+)["']?[^>]*>\s*</script\s*>""",
    re.IGNORECASE,
)


# Ends the page's script element wherever it appears, string literals included.
_SCRIPT_END = re.compile(r"</(script)", re.IGNORECASE)


@cache
def _kit(name: str) -> str:
    """The kit's code, safe inside a script element: `<\\/script` reads the same in a string."""
    code = (skills_folder() / "surfsense-html" / "kit" / KITS[name]).read_text(
        encoding="utf-8"
    )
    return _SCRIPT_END.sub(r"<\\/\1", code)


def with_kits(page: str) -> str:
    """The page with each kit it asks for written in; a kit that does not exist is refused."""
    for name in _ASKED.findall(page):
        if name not in KITS:
            named = ", ".join(f'"{kit}"' for kit in KITS)
            raise ToolCallError(
                f'There is no kit "{name}": a page can ask for {named}, as '
                '<script data-kit="fig"></script>.'
            )
    return _ASKED.sub(lambda asked: f"<script>\n{_kit(asked[1])}</script>", page)
