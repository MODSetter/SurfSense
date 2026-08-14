from app.tasks.chat.streaming.handlers.tools.activity import resolve_tool_activity


def test_save_artifact_uses_canonical_activity_presentation():
    activity = resolve_tool_activity("save_artifact", subagent_type=None)

    assert activity.active_title == "Preparing the file"
    assert activity.completed_title == "Presented file"
    assert activity.category == "artifact"
    assert activity.icon_key == "file-output"
