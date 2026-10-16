"""The Claude plan's generator, over one pool of warm runs for the API process.

A generator is made per request, so the pool cannot live on it. Only the API
answers text (ADR 0048), so one pool covers chat, titles and Studio.
"""

from claude_agent_sdk import ClaudeAgentOptions

from modules.llm.subscriptions.claude.chat import ClaudePlanProvider
from modules.llm.subscriptions.claude.chat_runs import ChatRuns
from modules.llm.subscriptions.claude.run import ClaudeRun, open_run
from shared.config import get_storage_settings

_runs: ChatRuns | None = None


async def _open(options: ClaudeAgentOptions) -> ClaudeRun:
    return await open_run(options)


def claude_generator() -> ClaudePlanProvider:
    global _runs
    if _runs is None:
        _runs = ChatRuns(_open)
    work_dir = get_storage_settings().data_dir / "claude" / "chat"
    work_dir.mkdir(parents=True, exist_ok=True)
    return ClaudePlanProvider(runs=_runs, work_dir=work_dir)


async def close_claude_runs() -> None:
    """Every warm run, when the API stops: no Claude Code outlives it."""
    global _runs
    if _runs is not None:
        await _runs.close_all()
        _runs = None
