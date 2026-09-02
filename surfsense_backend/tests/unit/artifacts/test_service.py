import pytest

from app.artifacts.service import (
    ArtifactFileInput,
    _artifact_format,
    _revision_metadata,
    _validate_files,
    _validated_files,
)


def test_validate_files_accepts_primary_and_rejects_duplicate_or_source_roles():
    primary = ArtifactFileInput(b"pdf", "out.pdf", "application/pdf", "primary")
    _validate_files([primary])

    with pytest.raises(ValueError, match="at most one"):
        _validate_files([primary, primary])
    with pytest.raises(ValueError, match=r"primary.*preview"):
        _validate_files(
            [ArtifactFileInput(b"source", "out.py", "text/x-python", "source")]
        )


def test_artifact_format_uses_markdown_or_primary_extension():
    assert _artifact_format([]) == "markdown"
    files = _validated_files(
        [ArtifactFileInput(b"pdf", "Report.PDF", "application/pdf")]
    )
    assert _artifact_format(files) == "pdf"


def test_flashcard_revision_removes_all_user_study_state():
    current = {
        "verification": {"verified": True},
        "flashcards": {
            "study_by_user": {
                "11": {
                    "generation": 1,
                    "marks": {"0": "good"},
                    "order": [1, 0],
                }
            },
        },
    }

    result = _revision_metadata(
        current,
        {"verification": {"verified": False}},
        artifact_format="flashcards",
    )

    assert result == {
        "verification": {"verified": False},
    }
    assert current["flashcards"]["study_by_user"]["11"]["marks"] == {"0": "good"}


def test_revision_removes_generation_scoped_quiz_state_across_format_switches():
    current = {
        "verification": {"verified": True},
        "quiz": {
            "progress_by_user": {
                "00000000-0000-0000-0000-000000000001": {
                    "generation": 1,
                    "mode": "all",
                    "active_question_indices": [0],
                    "answers": {"0": 2},
                }
            }
        },
        "flashcards": {"study_by_user": {}},
    }

    assert _revision_metadata(current, None, artifact_format="pdf") == {
        "verification": {"verified": True}
    }
