from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools.report import (
    create_generate_report_tool,
)


def test_legacy_generate_report_remains_callable():
    tool = create_generate_report_tool(workspace_id=1, thread_id=2)

    assert tool.name == "generate_report"
    assert tool.coroutine is not None
