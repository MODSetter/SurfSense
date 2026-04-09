"""Routes for user memory management (personal memory.md)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.llm_config import (
    create_chat_litellm_from_agent_config,
    load_agent_llm_config_for_search_space,
)
from app.agents.new_chat.tools.update_memory import MEMORY_HARD_LIMIT, _save_memory
from app.db import User, get_async_session
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter()


class MemoryRead(BaseModel):
    memory_md: str


class MemoryUpdate(BaseModel):
    memory_md: str


class MemoryEditRequest(BaseModel):
    query: str
    search_space_id: int


_MEMORY_EDIT_PROMPT = """\
You are a memory editor. The user wants to modify their memory document. \
Apply the user's instruction to the existing memory document and output the \
FULL updated document.

RULES:
1. If the instruction asks to add something, add it in the appropriate \
## section with a (YYYY-MM-DD) date prefix using today's date.
2. If the instruction asks to remove something, remove the matching entry.
3. If the instruction asks to change something, update the matching entry.
4. Preserve the existing ## section structure and all other entries.
5. Output ONLY the updated markdown — no explanations, no wrapping.

<current_memory>
{current_memory}
</current_memory>

<user_instruction>
{instruction}
</user_instruction>"""


@router.get("/users/me/memory", response_model=MemoryRead)
async def get_user_memory(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    await session.refresh(user, ["memory_md"])
    return MemoryRead(memory_md=user.memory_md or "")


@router.put("/users/me/memory", response_model=MemoryRead)
async def update_user_memory(
    body: MemoryUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    if len(body.memory_md) > MEMORY_HARD_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Memory exceeds {MEMORY_HARD_LIMIT:,} character limit ({len(body.memory_md):,} chars).",
        )
    user.memory_md = body.memory_md
    session.add(user)
    await session.commit()
    await session.refresh(user, ["memory_md"])
    return MemoryRead(memory_md=user.memory_md or "")


@router.post("/users/me/memory/edit", response_model=MemoryRead)
async def edit_user_memory(
    body: MemoryEditRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Apply a natural language edit to the user's personal memory via LLM."""
    agent_config = await load_agent_llm_config_for_search_space(
        session, body.search_space_id
    )
    if not agent_config:
        raise HTTPException(status_code=500, detail="No LLM configuration available.")
    llm = create_chat_litellm_from_agent_config(agent_config)
    if not llm:
        raise HTTPException(status_code=500, detail="Failed to create LLM instance.")

    await session.refresh(user, ["memory_md"])
    current_memory = user.memory_md or ""

    prompt = _MEMORY_EDIT_PROMPT.format(
        current_memory=current_memory or "(empty)",
        instruction=body.query,
    )
    try:
        response = await llm.ainvoke(
            [HumanMessage(content=prompt)],
            config={"tags": ["surfsense:internal", "memory-edit"]},
        )
        updated = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        ).strip()
    except Exception as e:
        logger.exception("Memory edit LLM call failed: %s", e)
        raise HTTPException(status_code=500, detail="Memory edit failed.") from e

    if not updated:
        raise HTTPException(status_code=400, detail="LLM returned empty result.")

    result = await _save_memory(
        updated_memory=updated,
        old_memory=current_memory,
        llm=llm,
        apply_fn=lambda content: setattr(user, "memory_md", content),
        commit_fn=session.commit,
        rollback_fn=session.rollback,
        label="memory",
        scope="user",
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    await session.refresh(user, ["memory_md"])
    return MemoryRead(memory_md=user.memory_md or "")
