"""Anonymous / free-chat agent.

The no-login chat experience: a deliberately minimal agent that bypasses the
full SurfSense deep-agent stack (filesystem, knowledge-base persistence,
subagents, skills, memory) and answers with an optional ``web_search`` tool and
an optional read-only uploaded document. See :mod:`.agent` for details.
"""

from app.agents.anonymous_chat.agent import (
    build_anonymous_system_prompt,
    create_anonymous_chat_agent,
)

__all__ = ["build_anonymous_system_prompt", "create_anonymous_chat_agent"]
