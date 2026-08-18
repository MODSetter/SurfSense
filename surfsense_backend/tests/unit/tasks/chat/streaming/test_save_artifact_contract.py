from app.tasks.chat.streaming.handlers.tools.activity import resolve_tool_activity


def test_save_artifact_uses_canonical_activity_presentation():
    activity = resolve_tool_activity(
        "save_artifact",
        subagent_type=None,
        trusted_descriptor={
            "active_title": "Preparing the file",
            "completed_title": "Presented file",
            "category": "artifact",
            "icon_key": "file-output",
            "kind": "save_artifact",
        },
    )

    assert activity.active_title == "Preparing the file"
    assert activity.completed_title == "Presented file"
    assert activity.category == "artifact"
    assert activity.icon_key == "file-output"
