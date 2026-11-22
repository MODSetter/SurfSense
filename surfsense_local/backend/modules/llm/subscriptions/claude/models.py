from pathlib import Path

from modules.llm.connections.serves import served_by
from modules.llm.connections.service import DiscoveredModel
from modules.llm.subscriptions.claude.account import CLAUDE_PLAN
from modules.llm.subscriptions.claude.launch import launch_options
from modules.llm.subscriptions.claude.run import open_run


async def claude_models(binary: Path, proxy_url: str | None) -> list[DiscoveredModel]:
    """What the account's Claude Code offers, each model once by its full id.

    The full id, not the alias Claude Code shows (`sonnet`), is what the
    manifest describes, so its window and capabilities apply; Claude Code
    accepts either.
    """
    run = await open_run(launch_options(binary, proxy_url=proxy_url, tools=[]))
    try:
        listed = await run.models()
    finally:
        await run.close()
    names = {m["resolvedModel"] for m in listed if m.get("resolvedModel")}
    return [
        DiscoveredModel(name, served_by(CLAUDE_PLAN), "declared")
        for name in sorted(names)
    ]
