"""Canonical read/write/reset/extract service for markdown memory."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSpace, User
from app.services.memory.prompts import (
    TEAM_MEMORY_EXTRACT_PROMPT,
    USER_MEMORY_EXTRACT_PROMPT,
)
from app.services.memory.rewrite import forced_rewrite
from app.services.memory.schemas import MemoryExtractionDecision, MemoryLimits
from app.services.memory.validation import (
    MEMORY_HARD_LIMIT,
    MEMORY_SOFT_LIMIT,
    soft_limit_warning,
    strip_preamble_to_first_heading,
    validate_bullet_format,
    validate_diff,
    validate_heading_sanity,
    validate_memory_scope,
    validate_memory_size,
)

logger = logging.getLogger(__name__)


class MemoryScope(StrEnum):
    USER = "user"
    TEAM = "team"


@dataclass(frozen=True)
class SaveResult:
    status: Literal["saved", "error", "no_op"]
    message: str
    memory_md: str = ""
    warnings: list[str] = field(default_factory=list)
    diff_warnings: list[str] = field(default_factory=list)
    format_warnings: list[str] = field(default_factory=list)
    notice: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "status": self.status,
            "message": self.message,
            "memory_md": self.memory_md,
        }
        if self.notice:
            data["notice"] = self.notice
        if self.warnings:
            data["warnings"] = self.warnings
            if len(self.warnings) == 1:
                data["warning"] = self.warnings[0]
        if self.diff_warnings:
            data["diff_warnings"] = self.diff_warnings
        if self.format_warnings:
            data["format_warnings"] = self.format_warnings
        return data


def memory_limits() -> MemoryLimits:
    return MemoryLimits(soft=MEMORY_SOFT_LIMIT, hard=MEMORY_HARD_LIMIT)


def _normalize_scope(scope: MemoryScope | str) -> MemoryScope:
    return scope if isinstance(scope, MemoryScope) else MemoryScope(scope)


def _normalize_user_id(target_id: str | UUID) -> UUID:
    return UUID(target_id) if isinstance(target_id, str) else target_id


async def _load_target(
    *,
    scope: MemoryScope | str,
    target_id: str | int | UUID,
    session: AsyncSession,
) -> User | SearchSpace | None:
    normalized = _normalize_scope(scope)
    if normalized is MemoryScope.USER:
        result = await session.execute(
            select(User).where(User.id == _normalize_user_id(target_id))  # type: ignore[arg-type]
        )
        return result.scalars().first()
    result = await session.execute(
        select(SearchSpace).where(SearchSpace.id == int(target_id))
    )
    return result.scalars().first()


def _get_memory(target: User | SearchSpace, scope: MemoryScope) -> str:
    if scope is MemoryScope.USER:
        return getattr(target, "memory_md", None) or ""
    return getattr(target, "shared_memory_md", None) or ""


def _set_memory(target: User | SearchSpace, scope: MemoryScope, content: str) -> None:
    if scope is MemoryScope.USER:
        target.memory_md = content
    else:
        target.shared_memory_md = content


async def read_memory(
    *,
    scope: MemoryScope | str,
    target_id: str | int | UUID,
    session: AsyncSession,
) -> str:
    normalized = _normalize_scope(scope)
    target = await _load_target(scope=normalized, target_id=target_id, session=session)
    if target is None:
        return ""
    return _get_memory(target, normalized)


async def save_memory(
    *,
    scope: MemoryScope | str,
    target_id: str | int | UUID,
    content: str,
    session: AsyncSession,
    llm: Any | None = None,
) -> SaveResult:
    normalized = _normalize_scope(scope)
    if not isinstance(content, str):
        return SaveResult(
            status="error",
            message="Internal error: memory payload must be a string.",
        )

    target = await _load_target(scope=normalized, target_id=target_id, session=session)
    if target is None:
        return SaveResult(
            status="error",
            message="User not found."
            if normalized is MemoryScope.USER
            else "Search space not found.",
        )

    old_memory = _get_memory(target, normalized)
    next_content = strip_preamble_to_first_heading(content.strip())
    notice: str | None = None
    warnings: list[str] = []

    if len(next_content) > MEMORY_HARD_LIMIT and llm is not None:
        rewritten = await forced_rewrite(next_content, llm)
        if rewritten is not None and len(rewritten) < len(next_content):
            next_content = strip_preamble_to_first_heading(rewritten)
            notice = "Memory was automatically rewritten to fit within limits."

    for validation in (
        validate_memory_size(next_content),
        validate_heading_sanity(next_content),
    ):
        if validation:
            return SaveResult(
                status="error",
                message=validation["message"],
                memory_md=old_memory,
            )

    scope_error, scope_warnings = validate_memory_scope(
        next_content,
        normalized.value,
        old_memory=old_memory,
    )
    warnings.extend(scope_warnings)
    if scope_error:
        return SaveResult(
            status="error",
            message=scope_error["message"],
            memory_md=old_memory,
            warnings=warnings,
        )

    try:
        _set_memory(target, normalized, next_content)
        session.add(target)
        await session.commit()
    except Exception as e:
        logger.exception("Failed to update %s memory: %s", normalized.value, e)
        await session.rollback()
        return SaveResult(
            status="error",
            message=f"Failed to update {normalized.value} memory: {e}",
            memory_md=old_memory,
        )

    diff_warnings = validate_diff(old_memory, next_content)
    format_warnings = validate_bullet_format(next_content)
    warning = soft_limit_warning(next_content)
    if warning:
        warnings.append(warning)

    return SaveResult(
        status="saved",
        message=(
            "Memory updated."
            if normalized is MemoryScope.USER
            else "Team memory updated."
        ),
        memory_md=next_content,
        warnings=warnings,
        diff_warnings=diff_warnings,
        format_warnings=format_warnings,
        notice=notice,
    )


async def reset_memory(
    *,
    scope: MemoryScope | str,
    target_id: str | int | UUID,
    session: AsyncSession,
) -> SaveResult:
    return await save_memory(
        scope=scope,
        target_id=target_id,
        content="",
        session=session,
        llm=None,
    )


async def extract_and_save(
    *,
    scope: MemoryScope | str,
    target_id: str | int | UUID,
    user_message: str,
    actor_display_name: str | None,
    session: AsyncSession,
    llm: Any,
) -> SaveResult:
    normalized = _normalize_scope(scope)
    current_memory = await read_memory(
        scope=normalized,
        target_id=target_id,
        session=session,
    )

    if normalized is MemoryScope.USER:
        first_name = (
            actor_display_name.strip().split()[0]
            if actor_display_name and actor_display_name.strip()
            else "The user"
        )
        prompt = USER_MEMORY_EXTRACT_PROMPT.format(
            current_memory=current_memory or "(empty)",
            user_message=user_message,
            user_name=first_name,
        )
    else:
        prompt = TEAM_MEMORY_EXTRACT_PROMPT.format(
            current_memory=current_memory or "(empty)",
            author=actor_display_name or "Unknown team member",
            user_message=user_message,
        )

    try:
        structured = llm.with_structured_output(MemoryExtractionDecision)
        decision = await structured.ainvoke(
            [HumanMessage(content=prompt)],
            config={"tags": ["surfsense:internal", "memory-extraction"]},
        )
    except Exception:
        logger.exception("Structured memory extraction failed")
        return SaveResult(
            status="error",
            message="Structured memory extraction failed.",
            memory_md=current_memory,
        )

    if decision.action == "no_update":
        return SaveResult(
            status="no_op",
            message=decision.reason or "No durable memory to persist.",
            memory_md=current_memory,
        )

    if not decision.updated_memory:
        return SaveResult(
            status="error",
            message="Structured memory extraction chose save without updated_memory.",
            memory_md=current_memory,
        )

    return await save_memory(
        scope=normalized,
        target_id=target_id,
        content=decision.updated_memory,
        session=session,
        llm=llm,
    )
