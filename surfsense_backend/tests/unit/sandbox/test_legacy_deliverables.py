from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools.index import (
    load_tools,
)


def test_legacy_report_and_resume_tools_are_not_registered(monkeypatch):
    monkeypatch.setattr("app.sandbox.is_sandbox_enabled", lambda: False)
    tools = load_tools(
        dependencies={
            "workspace_id": 1,
            "db_session": object(),
        }
    )

    names = {tool.name for tool in tools}
    assert "generate_report" not in names
    assert "generate_resume" not in names
