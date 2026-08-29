from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools.index import (
    config,
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


def test_video_authoring_tool_is_flag_gated(monkeypatch):
    monkeypatch.setattr("app.sandbox.is_sandbox_enabled", lambda: True)
    monkeypatch.setattr(config, "VIDEO_SANDBOX_RENDERING_ENABLED", False)
    dependencies = {"workspace_id": 1, "db_session": object()}

    legacy_names = {tool.name for tool in load_tools(dependencies=dependencies)}
    assert "generate_video_presentation" in legacy_names
    assert "synthesize_narration" not in legacy_names

    monkeypatch.setattr(config, "VIDEO_SANDBOX_RENDERING_ENABLED", True)
    sandbox_names = {tool.name for tool in load_tools(dependencies=dependencies)}
    assert "enqueue_deliverable_job" in sandbox_names
    assert "synthesize_narration" not in sandbox_names
    assert "generate_video_presentation" not in sandbox_names
