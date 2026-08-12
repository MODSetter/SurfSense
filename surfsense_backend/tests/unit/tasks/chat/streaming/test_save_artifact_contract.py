from app.tasks.chat.streaming.handlers.tools.deliverables.save_artifact.thinking import (
    resolve_start_thinking,
)


def test_artifact_id_marks_save_as_revision():
    thinking = resolve_start_thinking(
        "save_artifact",
        {"title": "Report", "artifact_id": 42},
    )

    assert thinking.title == "Revising artifact"


def test_document_id_does_not_mark_save_as_revision():
    thinking = resolve_start_thinking(
        "save_artifact",
        {"title": "Report", "document_id": 42},
    )

    assert thinking.title == "Saving artifact"
