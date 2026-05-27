"""``create_automation`` — NL intent → drafted JSON → HITL approval card → persisted.

Single tool that:

1. Drafts a structured automation from the user's intent via a focused sub-LLM
   (system prompt in :mod:`.prompt`).
2. Surfaces the validated draft in a HITL approval card
   (``action_type="automation_create"``).
3. On approval, validates the (possibly edited) payload again and persists
   it via :class:`AutomationService`.

The main agent only restates the user's request as a single ``intent`` string.
The drafting sub-LLM owns the JSON shape; the HITL card is the user's review.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from pydantic import ValidationError

from app.agents.new_chat.tools.hitl import request_approval
from app.automations.schemas.api import AutomationCreate
from app.automations.services.automation import AutomationService
from app.db import User, async_session_maker
from app.utils.content_utils import extract_text_content

from .prompt import build_draft_prompt

logger = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def create_create_automation_tool(
    *,
    search_space_id: int,
    user_id: str | UUID,
    llm: Any,
):
    """Factory for the ``create_automation`` tool.

    ``search_space_id`` is injected from the chat session (the model never
    has to guess it). ``llm`` is the drafting sub-model — we reuse the main
    agent's LLM and tag the call so it's identifiable in traces. A fresh
    ``AsyncSession`` is opened per call to avoid stale sessions on
    compiled-agent cache hits (same pattern as the Notion / memory tools).
    """
    uid = UUID(user_id) if isinstance(user_id, str) else user_id

    @tool
    async def create_automation(intent: str) -> dict[str, Any]:
        """Draft + save an automation from a natural-language intent.

        Use this when the user wants SurfSense to do something on its own
        on a schedule (e.g. "every morning summarize folder 12 to Slack").
        Restate the user's request as ONE concrete ``intent`` string: what
        should run, when, and which static values (folder ids, channel
        names, …) it needs.

        The tool drafts the full automation JSON internally, shows the user
        a structured preview on an approval card, and persists on approval.
        The card supports approve/reject only — if the user wants edits
        after seeing the draft, they say so in chat and you call this tool
        again with a refined intent. Do NOT prompt the user to confirm
        before calling — the card IS the confirmation.

        Args:
            intent: Concrete restatement of the user's request. Include
                the schedule (with timezone if mentioned), the action to
                take, and any static values. Example: "Every weekday at
                09:00 UTC, summarize new docs added to folder_id=12 since
                the last run, then post the summary to Slack channel
                '#daily-digest'."

        Returns:
            ``{"status": "saved", "automation_id": int, "name": str}`` on
            approval + save.
            ``{"status": "rejected", "message": "..."}`` when the user
            declines on the card.
            ``{"status": "invalid", "issues": [...], "raw": ...}`` when
            the drafter produced output that did not validate (call again
            with a more precise intent).
            ``{"status": "error", "message": "..."}`` on drafter or
            persistence failure.

            IMPORTANT: when status is ``"rejected"`` the user explicitly
            declined. Acknowledge once and stop — do NOT retry or pitch
            variants without a fresh user request.
        """
        # --- 1. Draft via sub-LLM ---
        prompt = build_draft_prompt(search_space_id=search_space_id, intent=intent)
        try:
            response = await llm.ainvoke(
                [HumanMessage(content=prompt)],
                config={"tags": ["surfsense:internal", "automation-draft"]},
            )
        except Exception as exc:
            logger.exception("create_automation drafting LLM call failed")
            return {"status": "error", "message": f"drafting failed: {exc}"}

        raw_text = extract_text_content(response.content).strip()
        draft = _extract_json(raw_text)
        if draft is None:
            return {
                "status": "invalid",
                "issues": ["model output was not parseable JSON"],
                "raw": raw_text,
            }

        # search_space_id is injected here so the sub-LLM never has to guess.
        draft["search_space_id"] = search_space_id
        try:
            validated_draft = AutomationCreate.model_validate(draft)
        except ValidationError as exc:
            return {
                "status": "invalid",
                "issues": _format_validation_issues(exc),
                "raw": draft,
            }

        # --- 2. HITL approval card ---
        try:
            card_params = validated_draft.model_dump(mode="json", by_alias=True)
            # search_space_id is session-scoped, not user-editable.
            card_params.pop("search_space_id", None)

            result = request_approval(
                action_type="automation_create",
                tool_name="create_automation",
                params=card_params,
                context={"search_space_id": search_space_id},
            )

            if result.rejected:
                return {
                    "status": "rejected",
                    "message": "User declined. Do not retry or suggest alternatives.",
                }

            # --- 3. Persist (re-validate in case the user edited) ---
            final_payload = {**result.params, "search_space_id": search_space_id}
            try:
                final_validated = AutomationCreate.model_validate(final_payload)
            except ValidationError as exc:
                return {
                    "status": "invalid",
                    "issues": _format_validation_issues(exc),
                }

            async with async_session_maker() as session:
                user = await session.get(User, uid)
                if user is None:
                    return {
                        "status": "error",
                        "message": "user not found in this session",
                    }
                service = AutomationService(session=session, user=user)
                created = await service.create(final_validated)
                return {
                    "status": "saved",
                    "automation_id": created.id,
                    "name": created.name,
                }

        except HTTPException as exc:
            return {"status": "error", "message": exc.detail}
        except Exception as exc:
            from langgraph.errors import GraphInterrupt

            if isinstance(exc, GraphInterrupt):
                raise
            logger.exception("create_automation failed")
            return {"status": "error", "message": f"persistence failed: {exc}"}

    return create_automation


def _extract_json(text: str) -> dict[str, Any] | None:
    """Pull a JSON object out of the model response, tolerating ``` fences."""
    if not text:
        return None
    candidate = text
    fence_match = _JSON_FENCE.search(text)
    if fence_match:
        candidate = fence_match.group(1)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _format_validation_issues(exc: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
        for err in exc.errors()
    ]
