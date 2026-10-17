"""Which engine runs an agent thread's turns: the one its session lives in."""

from sqlalchemy.orm import Session

from modules.agent.engines.agent_engine import AgentEngine
from modules.agent.engines.claude_code.engine import ClaudeCodeEngine
from modules.agent.engines.opencode_engine import OpencodeEngine
from modules.chat.models import AgentEngineKind, ChatThread
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.subscriptions.claude.account import CLAUDE_PLAN

_OPENCODE = OpencodeEngine()
_CLAUDE_CODE = ClaudeCodeEngine()


def thread_engine(thread: ChatThread) -> AgentEngine:
    if thread.agent_engine is AgentEngineKind.CLAUDE_CODE:
        return _CLAUDE_CODE
    return _OPENCODE


def selected_engine(session: Session) -> AgentEngine:
    """The engine the selected text model runs on: a Claude plan only through Claude Code."""
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    connection = selected.connection if selected is not None else None
    if connection is not None and connection.auth_kind == CLAUDE_PLAN:
        return _CLAUDE_CODE
    return _OPENCODE


def every_engine() -> tuple[AgentEngine, ...]:
    """For work that spans threads, such as deleting a workspace."""
    return (_OPENCODE, _CLAUDE_CODE)


async def close_engines() -> None:
    """Quit: end every Claude Code a thread kept running."""
    await _CLAUDE_CODE.close()
