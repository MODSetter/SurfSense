"""Baseline deep-agent factory without SurfSense specialist subagents.

Swap imports manually while building supervisor-style delegation::

    # from app.agents.new_chat.chat_deepagent import create_surfsense_deep_agent
    from app.agents.new_chat_supervisor_baseline.chat_deepagent import (
        create_surfsense_deep_agent,
    )

"""

from app.agents.new_chat_supervisor_baseline.chat_deepagent import (
    create_surfsense_deep_agent,
)

__all__ = ["create_surfsense_deep_agent"]
