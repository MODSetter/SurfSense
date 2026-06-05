"""Load markdown files shipped alongside a route package."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

_SHARED_SNIPPETS_PACKAGE = "app.agents.chat.multi_agent_chat.subagents.shared.snippets"


def read_md_file(package: str, stem: str) -> str:
    """Load ``{stem}.md`` from ``package`` via importlib resources, or return empty."""
    ref = resources.files(package).joinpath(f"{stem}.md")
    if not ref.is_file():
        return ""
    text = ref.read_text(encoding="utf-8")
    return text.rstrip("\n")


@lru_cache(maxsize=64)
def read_shared_snippet(name: str) -> str:
    """Load a shared markdown snippet from the snippets package.

    Cached because snippets are static at runtime and resolved many times
    (once per subagent build, plus per-subagent-per-route).
    """
    return read_md_file(_SHARED_SNIPPETS_PACKAGE, name)
