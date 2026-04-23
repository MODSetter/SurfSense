import pytest

from app.tasks.chat.stream_new_chat import (
    StreamResult,
    _contract_enforcement_active,
    _evaluate_file_contract_outcome,
    _tool_output_has_error,
)

pytestmark = pytest.mark.unit


def test_tool_output_error_detection():
    assert _tool_output_has_error("Error: failed to write file")
    assert _tool_output_has_error({"error": "boom"})
    assert _tool_output_has_error({"result": "Error: disk is full"})
    assert not _tool_output_has_error({"result": "Updated file /notes.md"})


def test_file_write_contract_outcome_reasons():
    result = StreamResult(intent_detected="file_write")
    passed, reason = _evaluate_file_contract_outcome(result)
    assert not passed
    assert reason == "no_write_attempt"

    result.write_attempted = True
    passed, reason = _evaluate_file_contract_outcome(result)
    assert not passed
    assert reason == "write_failed"

    result.write_succeeded = True
    passed, reason = _evaluate_file_contract_outcome(result)
    assert not passed
    assert reason == "verification_failed"

    result.verification_succeeded = True
    passed, reason = _evaluate_file_contract_outcome(result)
    assert passed
    assert reason == ""


def test_contract_enforcement_local_only():
    result = StreamResult(filesystem_mode="desktop_local_folder")
    assert _contract_enforcement_active(result)

    result.filesystem_mode = "cloud"
    assert not _contract_enforcement_active(result)

