"""Which engine runs an agent thread's turns."""

from modules.agent.engines.agent_engine import AgentEngine
from modules.agent.engines.opencode_engine import OpencodeEngine
from modules.chat.models import ChatThread

_OPENCODE = OpencodeEngine()


def thread_engine(thread: ChatThread) -> AgentEngine:
    """opencode, the only engine until a Claude plan model runs a thread."""
    return _OPENCODE


def every_engine() -> tuple[AgentEngine, ...]:
    """For work that spans threads, such as deleting a workspace."""
    return (_OPENCODE,)
