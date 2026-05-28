"""File-operation contract: when to enforce, how to score, how to log."""

from __future__ import annotations

import json
from typing import Any

from app.tasks.chat.streaming.shared.stream_result import StreamResult
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()


def contract_enforcement_active(result: StreamResult) -> bool:
    # Enforce only in desktop local-folder mode. Kept deterministic, no
    # env-driven progression modes.
    return result.filesystem_mode == "desktop_local_folder"


def evaluate_file_contract_outcome(result: StreamResult) -> tuple[bool, str]:
    if result.intent_detected != "file_write":
        return True, ""
    if not result.write_attempted:
        return False, "no_write_attempt"
    if not result.write_succeeded:
        return False, "write_failed"
    if not result.verification_succeeded:
        return False, "verification_failed"
    return True, ""


def log_file_contract(stage: str, result: StreamResult, **extra: Any) -> None:
    payload: dict[str, Any] = {
        "stage": stage,
        "request_id": result.request_id or "unknown",
        "turn_id": result.turn_id or "unknown",
        "chat_id": (
            result.turn_id.split(":", 1)[0] if ":" in result.turn_id else "unknown"
        ),
        "filesystem_mode": result.filesystem_mode,
        "client_platform": result.client_platform,
        "intent_detected": result.intent_detected,
        "intent_confidence": result.intent_confidence,
        "write_attempted": result.write_attempted,
        "write_succeeded": result.write_succeeded,
        "verification_succeeded": result.verification_succeeded,
        "commit_gate_passed": result.commit_gate_passed,
        "commit_gate_reason": result.commit_gate_reason or None,
    }
    payload.update(extra)
    _perf_log.info(
        "[file_operation_contract] %s", json.dumps(payload, ensure_ascii=False)
    )
