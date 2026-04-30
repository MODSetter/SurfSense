import inspect
import json
import logging
import re
from pathlib import Path

import pytest

import app.tasks.chat.stream_new_chat as stream_new_chat_module
from app.agents.new_chat.errors import BusyError
from app.agents.new_chat.middleware.busy_mutex import request_cancel, reset_cancel
from app.tasks.chat.stream_new_chat import (
    StreamResult,
    _classify_stream_exception,
    _contract_enforcement_active,
    _evaluate_file_contract_outcome,
    _log_chat_stream_error,
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


def _extract_chat_stream_payload(record_message: str) -> dict:
    prefix = "[chat_stream_error] "
    assert record_message.startswith(prefix)
    return json.loads(record_message[len(prefix) :])


def test_unified_chat_stream_error_log_schema(caplog):
    with caplog.at_level(logging.INFO, logger="app.tasks.chat.stream_new_chat"):
        _log_chat_stream_error(
            flow="new",
            error_kind="server_error",
            error_code="SERVER_ERROR",
            severity="warn",
            is_expected=False,
            request_id="req-123",
            thread_id=101,
            search_space_id=202,
            user_id="user-1",
            message="Error during chat: boom",
        )

    record = next(r for r in caplog.records if "[chat_stream_error]" in r.message)
    payload = _extract_chat_stream_payload(record.message)

    required_keys = {
        "event",
        "flow",
        "error_kind",
        "error_code",
        "severity",
        "is_expected",
        "request_id",
        "thread_id",
        "search_space_id",
        "user_id",
        "message",
    }
    assert required_keys.issubset(payload.keys())
    assert payload["event"] == "chat_stream_error"
    assert payload["flow"] == "new"
    assert payload["error_code"] == "SERVER_ERROR"


def test_premium_quota_uses_unified_chat_stream_log_shape(caplog):
    with caplog.at_level(logging.INFO, logger="app.tasks.chat.stream_new_chat"):
        _log_chat_stream_error(
            flow="resume",
            error_kind="premium_quota_exhausted",
            error_code="PREMIUM_QUOTA_EXHAUSTED",
            severity="info",
            is_expected=True,
            request_id="req-premium",
            thread_id=303,
            search_space_id=404,
            user_id="user-2",
            message="Buy more tokens to continue with this model, or switch to a free model",
            extra={"auto_fallback": False},
        )

    record = next(r for r in caplog.records if "[chat_stream_error]" in r.message)
    payload = _extract_chat_stream_payload(record.message)
    assert payload["event"] == "chat_stream_error"
    assert payload["error_kind"] == "premium_quota_exhausted"
    assert payload["error_code"] == "PREMIUM_QUOTA_EXHAUSTED"
    assert payload["flow"] == "resume"
    assert payload["is_expected"] is True
    assert payload["auto_fallback"] is False


def test_stream_error_emission_keeps_machine_error_codes():
    source = inspect.getsource(stream_new_chat_module)
    format_error_calls = re.findall(r"format_error\(", source)
    emitted_error_codes = set(re.findall(r'error_code="([A-Z_]+)"', source))

    # All stream paths should route through one shared terminal error emitter.
    assert len(format_error_calls) == 1
    assert {
        "PREMIUM_QUOTA_EXHAUSTED",
        "SERVER_ERROR",
    }.issubset(emitted_error_codes)
    assert 'flow: Literal["new", "regenerate"] = "new"' in source
    assert "_emit_stream_terminal_error" in source
    assert "flow=flow" in source
    assert 'flow="resume"' in source


def test_stream_exception_classifies_rate_limited():
    exc = Exception(
        '{"error":{"type":"rate_limit_error","message":"Rate limited. Please try again later."}}'
    )
    kind, code, severity, is_expected, user_message, extra = _classify_stream_exception(
        exc, flow_label="chat"
    )
    assert kind == "rate_limited"
    assert code == "RATE_LIMITED"
    assert severity == "warn"
    assert is_expected is True
    assert "temporarily rate-limited" in user_message
    assert extra is None


def test_stream_exception_classifies_thread_busy():
    exc = BusyError(request_id="thread-123")
    kind, code, severity, is_expected, user_message, extra = _classify_stream_exception(
        exc, flow_label="chat"
    )
    assert kind == "thread_busy"
    assert code == "THREAD_BUSY"
    assert severity == "warn"
    assert is_expected is True
    assert "still finishing for this thread" in user_message
    assert extra is None


def test_stream_exception_classifies_thread_busy_from_message():
    exc = Exception("Thread is busy with another request")
    kind, code, severity, is_expected, user_message, extra = _classify_stream_exception(
        exc, flow_label="chat"
    )
    assert kind == "thread_busy"
    assert code == "THREAD_BUSY"
    assert severity == "warn"
    assert is_expected is True
    assert "still finishing for this thread" in user_message
    assert extra is None


def test_stream_exception_classifies_turn_cancelling_when_cancel_requested():
    thread_id = "thread-cancelling-1"
    reset_cancel(thread_id)
    request_cancel(thread_id)
    exc = BusyError(request_id=thread_id)
    kind, code, severity, is_expected, user_message, extra = _classify_stream_exception(
        exc, flow_label="chat"
    )
    assert kind == "thread_busy"
    assert code == "TURN_CANCELLING"
    assert severity == "info"
    assert is_expected is True
    assert "stopping" in user_message
    assert isinstance(extra, dict)
    assert "retry_after_ms" in extra


def test_premium_classification_is_error_code_driven():
    classifier_path = Path(__file__).resolve().parents[3] / "surfsense_web/lib/chat/chat-error-classifier.ts"
    source = classifier_path.read_text(encoding="utf-8")

    assert "PREMIUM_KEYWORDS" not in source
    assert "RATE_LIMIT_KEYWORDS" not in source
    assert "normalized.includes(" not in source
    assert 'if (errorCode === "PREMIUM_QUOTA_EXHAUSTED") {' in source


def test_stream_terminal_error_handler_has_pre_accept_soft_rollback_hook():
    page_path = (
        Path(__file__).resolve().parents[3]
        / "surfsense_web/app/dashboard/[search_space_id]/new-chat/[[...chat_id]]/page.tsx"
    )
    source = page_path.read_text(encoding="utf-8")

    assert "onPreAcceptFailure?: () => Promise<void>;" in source
    assert "if (!accepted) {" in source
    assert "await onPreAcceptFailure?.();" in source
    assert "await onAcceptedStreamError?.();" in source
    assert "setMessages((prev) => prev.filter((m) => m.id !== userMsgId));" in source
    assert "setMessageDocumentsMap((prev) => {" in source


def test_toast_only_pre_accept_policy_has_no_inline_failed_marker():
    user_message_path = (
        Path(__file__).resolve().parents[3] / "surfsense_web/components/assistant-ui/user-message.tsx"
    )
    source = user_message_path.read_text(encoding="utf-8")

    assert "Not sent. Edit and retry." not in source
    assert "failed_pre_accept" not in source


def test_network_send_failures_use_unified_retry_toast_message():
    classifier_path = Path(__file__).resolve().parents[3] / "surfsense_web/lib/chat/chat-error-classifier.ts"
    classifier_source = classifier_path.read_text(encoding="utf-8")
    request_errors_path = (
        Path(__file__).resolve().parents[3] / "surfsense_web/lib/chat/chat-request-errors.ts"
    )
    request_errors_source = request_errors_path.read_text(encoding="utf-8")

    assert '"send_failed_pre_accept"' in classifier_source
    assert 'errorCode === "SEND_FAILED_PRE_ACCEPT"' in classifier_source
    assert 'errorCode === "TURN_CANCELLING"' in classifier_source
    assert "if (withCode.code) return withCode.code;" in classifier_source
    assert 'userMessage: "Message not sent. Please retry."' in classifier_source
    assert 'userMessage: "Connection issue. Please try again."' in classifier_source
    assert "const passthroughCodes = new Set([" in request_errors_source
    assert '"PREMIUM_QUOTA_EXHAUSTED"' in request_errors_source
    assert '"THREAD_BUSY"' in request_errors_source
    assert '"TURN_CANCELLING"' in request_errors_source
    assert '"AUTH_EXPIRED"' in request_errors_source
    assert '"UNAUTHORIZED"' in request_errors_source
    assert '"RATE_LIMITED"' in request_errors_source
    assert '"NETWORK_ERROR"' in request_errors_source
    assert '"STREAM_PARSE_ERROR"' in request_errors_source
    assert '"TOOL_EXECUTION_ERROR"' in request_errors_source
    assert '"PERSIST_MESSAGE_FAILED"' in request_errors_source
    assert '"SERVER_ERROR"' in request_errors_source
    assert "passthroughCodes.has(existingCode)" in request_errors_source
    assert 'errorCode: "SEND_FAILED_PRE_ACCEPT"' in request_errors_source
    assert 'errorCode: "NETWORK_ERROR"' not in request_errors_source
    assert "Failed to start chat. Please try again." not in classifier_source


def test_pre_post_accept_abort_contract_exists_for_new_resume_regenerate_flows():
    page_path = (
        Path(__file__).resolve().parents[3]
        / "surfsense_web/app/dashboard/[search_space_id]/new-chat/[[...chat_id]]/page.tsx"
    )
    source = page_path.read_text(encoding="utf-8")

    # Each flow tracks accepted boundary and passes it into shared terminal handling.
    assert "let newAccepted = false;" in source
    assert "let resumeAccepted = false;" in source
    assert "let regenerateAccepted = false;" in source
    assert "accepted: newAccepted," in source
    assert "accepted: resumeAccepted," in source
    assert "accepted: regenerateAccepted," in source

    # Pre-accept abort in resume/regenerate exits without persistence.
    assert "if (!resumeAccepted) return;" in source
    assert "if (!regenerateAccepted) return;" in source

    # New flow persists only when accepted and not already persisted.
    assert "if (newAccepted && !userPersisted) {" in source
    assert "const fetchWithTurnCancellingRetry = useCallback(" in source
    assert "computeFallbackTurnCancellingRetryDelay" in source
    assert 'withMeta.errorCode === "TURN_CANCELLING"' in source
    assert 'withMeta.errorCode === "THREAD_BUSY"' in source
    assert "await fetchWithTurnCancellingRetry(() =>" in source


def test_cancel_active_turn_route_contract_exists():
    routes_path = (
        Path(__file__).resolve().parents[3]
        / "surfsense_backend/app/routes/new_chat_routes.py"
    )
    source = routes_path.read_text(encoding="utf-8")

    assert '@router.post(\n    "/threads/{thread_id}/cancel-active-turn",' in source
    assert "response_model=CancelActiveTurnResponse" in source
    assert 'status="cancelling",' in source
    assert 'error_code="TURN_CANCELLING",' in source
    assert "retry_after_ms=retry_after_ms if retry_after_ms > 0 else None," in source
    assert "retry_after_at=" in source
    assert 'status="idle",' in source
    assert 'error_code="NO_ACTIVE_TURN",' in source


def test_turn_status_route_contract_exists():
    routes_path = (
        Path(__file__).resolve().parents[3]
        / "surfsense_backend/app/routes/new_chat_routes.py"
    )
    source = routes_path.read_text(encoding="utf-8")

    assert '@router.get(\n    "/threads/{thread_id}/turn-status",' in source
    assert "response_model=TurnStatusResponse" in source
    assert "_build_turn_status_payload(thread_id)" in source
    assert "Permission.CHATS_READ.value" in source
    assert "_raise_if_thread_busy_for_start(" in source


def test_turn_cancelling_retry_policy_contract_exists():
    routes_path = (
        Path(__file__).resolve().parents[3]
        / "surfsense_backend/app/routes/new_chat_routes.py"
    )
    source = routes_path.read_text(encoding="utf-8")

    assert "TURN_CANCELLING_INITIAL_DELAY_MS = 200" in source
    assert "TURN_CANCELLING_BACKOFF_FACTOR = 2" in source
    assert "TURN_CANCELLING_MAX_DELAY_MS = 1500" in source
    assert "def _compute_turn_cancelling_retry_delay(" in source
    assert "retry-after-ms" in source
    assert '"Retry-After"' in source
    assert '"errorCode": "TURN_CANCELLING"' in source


def test_turn_status_sse_contract_exists():
    stream_source = (
        Path(__file__).resolve().parents[3]
        / "surfsense_backend/app/tasks/chat/stream_new_chat.py"
    ).read_text(encoding="utf-8")
    state_source = (
        Path(__file__).resolve().parents[3] / "surfsense_web/lib/chat/streaming-state.ts"
    ).read_text(encoding="utf-8")
    pipeline_source = (
        Path(__file__).resolve().parents[3] / "surfsense_web/lib/chat/stream-pipeline.ts"
    ).read_text(encoding="utf-8")

    assert '"turn-status"' in stream_source
    assert '"status": "busy"' in stream_source
    assert '"status": "idle"' in stream_source
    assert "type: \"data-turn-status\"" in state_source
    assert "case \"data-turn-status\":" in pipeline_source
    assert "end_turn(str(chat_id))" in stream_source
