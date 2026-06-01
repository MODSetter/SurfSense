"""Build and emit the first ``thinking-1`` step for a new-chat turn.

The step title and "Processing X" items are derived from what the user sent
(text snippet, image count) so the FE can render a meaningful placeholder
while the agent stream warms up.

``thinking-1`` is the canonical id for this step — every subsequent
``thinking-N`` produced by ``stream_agent_events`` folds into the same
singleton ``data-thinking-steps`` part on the FE.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.services.new_streaming_service import VercelStreamingService


@dataclass
class InitialThinkingStep:
    """Resolved fields passed both into the SSE frame and the builder hook.

    ``items`` is the bullet list under the step title; ``title`` is the
    one-line step header. ``step_id`` is hard-coded ``thinking-1`` so the FE
    Timeline can de-duplicate against the prior assistant message on resume.
    """

    step_id: str
    title: str
    items: list[str]


def build_initial_thinking_step(
    *,
    user_query: str,
    user_image_data_urls: list[str] | None,
) -> InitialThinkingStep:
    title = "Understanding your request"
    action_verb = "Processing"

    processing_parts: list[str] = []
    if user_query.strip():
        query_text = user_query[:80] + ("..." if len(user_query) > 80 else "")
        processing_parts.append(query_text)
    elif user_image_data_urls:
        processing_parts.append(f"[{len(user_image_data_urls)} image(s)]")
    else:
        processing_parts.append("(message)")

    items = [f"{action_verb}: {' '.join(processing_parts)}"]
    return InitialThinkingStep(step_id="thinking-1", title=title, items=items)


def iter_initial_thinking_step_frame(
    step: InitialThinkingStep,
    *,
    streaming_service: VercelStreamingService,
    content_builder: Any | None,
) -> Iterator[str]:
    """Drive both the SSE emission and the builder hook for the initial step.

    The FE folds this step into the same singleton ``data-thinking-steps`` part
    as everything the agent stream emits later, so we mirror that fold
    server-side by driving the builder lifecycle ourselves.
    """
    if content_builder is not None:
        content_builder.on_thinking_step(
            step.step_id, step.title, "in_progress", step.items
        )
    yield streaming_service.format_thinking_step(
        step_id=step.step_id,
        title=step.title,
        status="in_progress",
        items=step.items,
    )
