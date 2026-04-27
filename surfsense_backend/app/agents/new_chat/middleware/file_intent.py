"""Semantic file-intent routing middleware for new chat turns.

This middleware classifies the latest human turn into a small intent set:
- chat_only
- file_write
- file_read

For ``file_write`` turns it injects a strict system contract so the model
uses filesystem tools before claiming success, and provides a deterministic
fallback path when no filename is specified by the user.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class FileOperationIntent(StrEnum):
    CHAT_ONLY = "chat_only"
    FILE_WRITE = "file_write"
    FILE_READ = "file_read"


class FileIntentPlan(BaseModel):
    intent: FileOperationIntent = Field(
        description="Primary user intent for this turn."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.5,
        description="Model confidence in the selected intent.",
    )
    suggested_filename: str | None = Field(
        default=None,
        description="Optional filename (e.g. notes.md) inferred from user request.",
    )
    suggested_directory: str | None = Field(
        default=None,
        description=(
            "Optional directory path (e.g. /reports/q2 or reports/q2) inferred from "
            "user request."
        ),
    )
    suggested_path: str | None = Field(
        default=None,
        description=(
            "Optional full file path (e.g. /reports/q2/summary.md). If present, this "
            "takes precedence over suggested_directory + suggested_filename."
        ),
    )


def _extract_text_from_message(message: BaseMessage) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part)
    return str(content)


def _extract_json_payload(text: str) -> str:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _sanitize_filename(value: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip()
    name = re.sub(r"\s+", "-", name)
    name = name.strip("._-")
    if not name:
        name = "note"
    if len(name) > 80:
        name = name[:80].rstrip("-_.")
    return name


def _sanitize_path_segment(value: str) -> str:
    segment = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip()
    segment = re.sub(r"\s+", "_", segment)
    segment = segment.strip("._-")
    return segment


def _normalize_directory(value: str) -> str:
    raw = value.strip().replace("\\", "/")
    raw = raw.strip("/")
    if not raw:
        return ""
    parts = [_sanitize_path_segment(part) for part in raw.split("/") if part.strip()]
    parts = [part for part in parts if part]
    return "/".join(parts)


def _normalize_file_path(value: str) -> str:
    raw = value.strip().replace("\\", "/").strip()
    if not raw:
        return ""
    had_trailing_slash = raw.endswith("/")
    raw = raw.strip("/")
    if not raw:
        return ""
    parts = [_sanitize_path_segment(part) for part in raw.split("/") if part.strip()]
    parts = [part for part in parts if part]
    if not parts:
        return ""
    if had_trailing_slash:
        return f"/{'/'.join(parts)}/"
    return f"/{'/'.join(parts)}"


def _infer_directory_from_user_text(user_text: str) -> str | None:
    patterns = (
        r"\b(?:in|inside|under)\s+(?:the\s+)?([a-zA-Z0-9 _\-/]+?)\s+folder\b",
        r"\b(?:in|inside|under)\s+([a-zA-Z0-9 _\-/]+?)\b",
    )
    lowered = user_text.lower()
    for pattern in patterns:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1).strip()
        if candidate in {"the", "a", "an"}:
            continue
        normalized = _normalize_directory(candidate)
        if normalized:
            return normalized
    return None


def _fallback_path(
    suggested_filename: str | None,
    *,
    suggested_directory: str | None = None,
    suggested_path: str | None = None,
    user_text: str,
) -> str:
    inferred_dir = _infer_directory_from_user_text(user_text)

    sanitized_filename = ""
    if suggested_filename:
        sanitized_filename = _sanitize_filename(suggested_filename)
        if sanitized_filename.lower().endswith(".txt"):
            sanitized_filename = f"{sanitized_filename[:-4]}.md"
    if not sanitized_filename:
        sanitized_filename = "notes.md"
    elif "." not in sanitized_filename:
        sanitized_filename = f"{sanitized_filename}.md"

    normalized_suggested_path = (
        _normalize_file_path(suggested_path) if suggested_path else ""
    )
    if normalized_suggested_path:
        if normalized_suggested_path.endswith("/"):
            return f"{normalized_suggested_path.rstrip('/')}/{sanitized_filename}"
        return normalized_suggested_path

    directory = _normalize_directory(suggested_directory or "")
    if not directory and inferred_dir:
        directory = inferred_dir
    if directory:
        return f"/{directory}/{sanitized_filename}"

    return f"/{sanitized_filename}"


def _build_classifier_prompt(*, recent_conversation: str, user_text: str) -> str:
    return (
        "Classify the latest user request into a filesystem intent for an AI agent.\n"
        "Return JSON only with this exact schema:\n"
        '{"intent":"chat_only|file_write|file_read","confidence":0.0,"suggested_filename":"string or null","suggested_directory":"string or null","suggested_path":"string or null"}\n\n'
        "Rules:\n"
        "- Use semantic intent, not literal keywords.\n"
        "- file_write: user asks to create/save/write/update/edit content as a file.\n"
        "- file_read: user asks to open/read/list/search existing files.\n"
        "- chat_only: conversational/analysis responses without required file operations.\n"
        "- For file_write, choose a concise semantic suggested_filename and match the requested format.\n"
        "- If the user mentions a folder/directory, populate suggested_directory.\n"
        "- If user specifies an explicit full path, populate suggested_path.\n"
        "- Use extensions that match user intent (e.g. .md, .json, .yaml, .csv, .py, .ts, .js, .html, .css, .sql).\n"
        "- Do not use .txt; prefer .md for generic text notes.\n"
        "- Do not include dates or timestamps in suggested_filename unless explicitly requested.\n"
        "- Never include markdown or explanation.\n\n"
        f"Recent conversation:\n{recent_conversation or '(none)'}\n\n"
        f"Latest user message:\n{user_text}"
    )


def _build_recent_conversation(messages: list[BaseMessage], *, max_messages: int = 6) -> str:
    rows: list[str] = []
    for msg in messages[-max_messages:]:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        text = re.sub(r"\s+", " ", _extract_text_from_message(msg)).strip()
        if text:
            rows.append(f"{role}: {text[:280]}")
    return "\n".join(rows)


class FileIntentMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Classify file intent and inject a strict file-write contract."""

    tools = ()

    def __init__(self, *, llm: BaseChatModel | None = None) -> None:
        self.llm = llm

    async def _classify_intent(
        self, *, messages: list[BaseMessage], user_text: str
    ) -> FileIntentPlan:
        if self.llm is None:
            return FileIntentPlan(intent=FileOperationIntent.CHAT_ONLY, confidence=0.0)

        prompt = _build_classifier_prompt(
            recent_conversation=_build_recent_conversation(messages),
            user_text=user_text,
        )
        try:
            response = await self.llm.ainvoke(
                [HumanMessage(content=prompt)],
                config={"tags": ["surfsense:internal"]},
            )
            payload = json.loads(_extract_json_payload(_extract_text_from_message(response)))
            plan = FileIntentPlan.model_validate(payload)
            return plan
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.warning("File intent classifier returned invalid output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("File intent classifier failed: %s", exc)

        return FileIntentPlan(intent=FileOperationIntent.CHAT_ONLY, confidence=0.0)

    async def abefore_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        messages = state.get("messages") or []
        if not messages:
            return None

        last_human: HumanMessage | None = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_human = msg
                break
        if last_human is None:
            return None

        user_text = _extract_text_from_message(last_human).strip()
        if not user_text:
            return None

        plan = await self._classify_intent(messages=messages, user_text=user_text)
        suggested_path = _fallback_path(
            plan.suggested_filename,
            suggested_directory=plan.suggested_directory,
            suggested_path=plan.suggested_path,
            user_text=user_text,
        )
        contract = {
            "intent": plan.intent.value,
            "confidence": plan.confidence,
            "suggested_path": suggested_path,
            "timestamp": datetime.now(UTC).isoformat(),
            "turn_id": state.get("turn_id", ""),
        }

        if plan.intent != FileOperationIntent.FILE_WRITE:
            return {"file_operation_contract": contract}

        contract_msg = SystemMessage(
            content=(
                "<file_operation_contract>\n"
                "This turn intent is file_write.\n"
                f"Suggested default path: {suggested_path}\n"
                "Rules:\n"
                "- You MUST call write_file or edit_file before claiming success.\n"
                "- If no path is provided by the user, use the suggested default path.\n"
                "- Do not claim a file was created/updated unless tool output confirms it.\n"
                "- If the write/edit fails, clearly report failure instead of success.\n"
                "- Do not include timestamps or dates in generated file content unless the user explicitly asks for them.\n"
                "- For open-ended requests (e.g., random note), generate useful concrete content, not placeholders.\n"
                "</file_operation_contract>"
            )
        )

        # Insert just before the latest human turn so it applies to this request.
        new_messages = list(messages)
        insert_at = max(len(new_messages) - 1, 0)
        new_messages.insert(insert_at, contract_msg)
        return {"messages": new_messages, "file_operation_contract": contract}

