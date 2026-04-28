"""
SurfSense compaction middleware.

Subclasses :class:`deepagents.middleware.summarization.SummarizationMiddleware`
to add SurfSense-specific behavior:

1. **Structured summary template** (OpenCode-style ``## Goal / Constraints /
   Progress / Key Decisions / Next Steps / Critical Context / Relevant Files``).
2. **Protect SurfSense-specific SystemMessages** so injected hints
   (``<priority_documents>``, ``<workspace_tree>``, ``<file_operation_contract>``,
   ``<user_memory>``, ``<team_memory>``, ``<user_name>``, ``<memory_warning>``)
   are *not* summarized away and are kept verbatim in the post-summary
   message list.
3. **Sanitize ``content=None``** when feeding messages into ``get_buffer_string``
   (Azure OpenAI / LiteLLM defense — when a provider streams an AIMessage
   containing only tool_calls and no text, ``content`` can be ``None`` and
   ``get_buffer_string`` crashes iterating over ``None``). This used to live in
   ``safe_summarization.py``; folded in here.

This replaces ``app.agents.new_chat.middleware.safe_summarization``.

Tier 1.3 in the OpenCode-port plan.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from deepagents.middleware.summarization import (
    SummarizationMiddleware,
    compute_summarization_defaults,
)
from langchain_core.messages import SystemMessage

from app.observability import otel as ot

if TYPE_CHECKING:
    from deepagents.backends.protocol import BACKEND_TYPES
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import AnyMessage

logger = logging.getLogger(__name__)

# OpenCode-faithful structured summary template. Mirrors
# ``opencode/packages/opencode/src/session/compaction.ts:40-75``. Kept as a
# module-level constant so unit tests can assert on its sections.
SURFSENSE_SUMMARY_PROMPT = """<role>
SurfSense Conversation Compaction Assistant
</role>

<primary_objective>
Extract the most important context from the conversation history below into a structured summary that will replace the older messages.
</primary_objective>

<instructions>
You are running because the conversation has grown beyond the model's input window. The conversation history below will be summarized and replaced with your output. Use the structured template that follows; keep each section concise but comprehensive enough that the agent can resume work without losing context. Each section is a checklist — populate it with relevant content or write "None" if there is nothing to report.

## Goal
What is the user's primary goal or request? State it in one or two sentences.

## Constraints
What boundaries must the agent respect (citations rules, visibility scope, allowed tools, user-imposed style, deadlines, deny-listed topics)?

## Progress
What has the agent already accomplished? List each completed step succinctly. Do not reproduce tool output; just record the conclusion.

## Key Decisions
What choices were made and why? Include rejected alternatives and the reasoning behind selecting the current path.

## Next Steps
What specific tasks remain to achieve the goal? Order them by dependency.

## Critical Context
What facts, IDs, document titles, query keywords, error messages, or partial answers must persist into the next turn? Include verbatim quotes only when the exact wording matters (e.g. a precise filter clause or a literal name).

## Relevant Files
What documents or paths in the SurfSense knowledge base are in play? Use ``/documents/...`` paths exactly as they appeared in the workspace tree.
</instructions>

<messages>
Messages to summarize:
{messages}
</messages>

Respond ONLY with the structured summary. Do not include any text before or after.
"""

# SystemMessage prefixes that must NOT be summarized away. They are
# re-injected on every turn by the corresponding middleware, but the
# compaction step happens *before* re-injection in some paths, so we
# must preserve them verbatim across the cutoff.
PROTECTED_SYSTEM_PREFIXES: tuple[str, ...] = (
    "<priority_documents>",  # KnowledgePriorityMiddleware
    "<workspace_tree>",  # KnowledgeTreeMiddleware
    "<file_operation_contract>",  # FileIntentMiddleware
    "<user_memory>",  # MemoryInjectionMiddleware
    "<team_memory>",  # MemoryInjectionMiddleware
    "<user_name>",  # MemoryInjectionMiddleware
    "<memory_warning>",  # MemoryInjectionMiddleware
)


def _is_protected_system_message(msg: AnyMessage) -> bool:
    """Return True if ``msg`` is a SystemMessage we must not summarize."""
    if not isinstance(msg, SystemMessage):
        return False
    content = msg.content
    if not isinstance(content, str):
        return False
    stripped = content.lstrip()
    return any(stripped.startswith(prefix) for prefix in PROTECTED_SYSTEM_PREFIXES)


def _sanitize_message_content(msg: AnyMessage) -> AnyMessage:
    """Return ``msg`` with ``content=None`` coerced to ``""``.

    Folds in the historical defense from ``safe_summarization.py`` —
    ``get_buffer_string`` reads ``m.text`` which iterates ``self.content``,
    so a ``None`` content (Azure OpenAI / LiteLLM streaming a tool-only
    AIMessage) explodes. We return a copy with empty string content so
    downstream consumers see an empty body without mutating the original.
    """
    if getattr(msg, "content", "not-missing") is not None:
        return msg
    try:
        return msg.model_copy(update={"content": ""})
    except AttributeError:
        import copy

        new_msg = copy.copy(msg)
        try:
            new_msg.content = ""
        except Exception:
            logger.debug(
                "Could not sanitize content=None on message of type %s",
                type(msg).__name__,
            )
            return msg
        return new_msg


class SurfSenseCompactionMiddleware(SummarizationMiddleware):
    """SummarizationMiddleware tuned for SurfSense.

    Notes
    -----
    - Overrides :meth:`_partition_messages` so protected SystemMessages
      survive into the ``preserved_messages`` half regardless of cutoff.
    - Overrides :meth:`_filter_summary_messages` so the buffer-string path
      never iterates ``None`` content.
    - Inherits everything else (auto-trigger, backend offload,
      ``_summarization_event`` plumbing, ``ContextOverflowError`` fallback).
    """

    def _partition_messages(  # type: ignore[override]
        self,
        conversation_messages: list[AnyMessage],
        cutoff_index: int,
    ) -> tuple[list[AnyMessage], list[AnyMessage]]:
        """Split messages but always preserve SurfSense protected SystemMessages.

        Mirrors OpenCode's ``PRUNE_PROTECTED_TOOLS`` philosophy
        (``opencode/packages/opencode/src/session/compaction.ts``): some
        message types are always kept verbatim because they are part of the
        agent's working contract, not transient output.

        Also opens a ``compaction.run`` OTel span (no-op when OTel is off)
        so dashboards can count compaction events and message-volume
        without having to instrument upstream callers.
        """
        # Opening a span here is appropriate because partitioning is the
        # first call SummarizationMiddleware makes when it has decided to
        # summarize; we record the volume and then close as a normal span.
        with ot.compaction_span(
            reason="auto",
            messages_in=len(conversation_messages),
            extra={"compaction.cutoff_index": int(cutoff_index)},
        ):
            messages_to_summarize, preserved_messages = (
                super()._partition_messages(conversation_messages, cutoff_index)
            )

            protected: list[AnyMessage] = []
            kept_for_summary: list[AnyMessage] = []
            for msg in messages_to_summarize:
                if _is_protected_system_message(msg):
                    protected.append(msg)
                else:
                    kept_for_summary.append(msg)

            # Place protected blocks at the *front* of preserved_messages so
            # they keep their original ordering relative to the summary
            # HumanMessage that precedes the rest of the preserved tail.
            return kept_for_summary, [*protected, *preserved_messages]

    def _filter_summary_messages(  # type: ignore[override]
        self, messages: list[AnyMessage]
    ) -> list[AnyMessage]:
        """Filter previous summaries AND sanitize ``content=None``.

        Folds the ``safe_summarization.py`` defense in: when the buffer
        builder iterates ``m.text`` over ``None`` it explodes; sanitizing
        here covers both the sync and async offload paths.
        """
        filtered = super()._filter_summary_messages(messages)
        return [_sanitize_message_content(m) for m in filtered]


def create_surfsense_compaction_middleware(
    model: BaseChatModel,
    backend: BACKEND_TYPES,
    *,
    summary_prompt: str | None = None,
    history_path_prefix: str = "/conversation_history",
    **overrides: Any,
) -> SurfSenseCompactionMiddleware:
    """Build a :class:`SurfSenseCompactionMiddleware` with sensible defaults.

    Pulls profile-aware ``trigger`` / ``keep`` / ``truncate_args_settings``
    via :func:`deepagents.middleware.summarization.compute_summarization_defaults`
    so callers get the same behavior as ``create_summarization_middleware``
    plus our overrides.

    Args:
        model: Chat model to call for summary generation.
        backend: Backend instance or factory for offloading conversation history.
        summary_prompt: Optional override; defaults to :data:`SURFSENSE_SUMMARY_PROMPT`.
        history_path_prefix: Path prefix for offloaded conversation history.
        **overrides: Forwarded to :class:`SurfSenseCompactionMiddleware`.
    """
    defaults = compute_summarization_defaults(model)
    return SurfSenseCompactionMiddleware(
        model=model,
        backend=backend,
        trigger=overrides.pop("trigger", defaults["trigger"]),
        keep=overrides.pop("keep", defaults["keep"]),
        trim_tokens_to_summarize=overrides.pop("trim_tokens_to_summarize", None),
        truncate_args_settings=overrides.pop(
            "truncate_args_settings", defaults["truncate_args_settings"]
        ),
        summary_prompt=summary_prompt or SURFSENSE_SUMMARY_PROMPT,
        history_path_prefix=history_path_prefix,
        **overrides,
    )


__all__ = [
    "PROTECTED_SYSTEM_PREFIXES",
    "SURFSENSE_SUMMARY_PROMPT",
    "SurfSenseCompactionMiddleware",
    "create_surfsense_compaction_middleware",
]
