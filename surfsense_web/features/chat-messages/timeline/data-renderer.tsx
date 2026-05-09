"use client";

import { makeAssistantDataUI, useAuiState } from "@assistant-ui/react";
import { useMemo } from "react";
import { buildTimeline, type ThinkingStepInput } from "./build-timeline";
import { Timeline } from "./timeline";

/**
 * assistant-ui data UI for the ``thinking-steps`` data-part. Receives
 * the relay's step array as ``data``, reads message ``content`` via
 * ``useAuiState``, builds the unified ``TimelineItem[]`` once
 * (``buildTimeline`` is pure), and renders the ``Timeline``.
 *
 * ``isMessageStreaming`` is the AND of thread-running + this-message-
 * is-last; that flag drives the ``isThreadRunning`` runtime override
 * in ``Timeline`` (stale "running" → "completed" once the thread
 * stops). Mirrors the legacy ``ThinkingStepsDataRenderer`` semantics.
 */
function TimelineDataRenderer({ data }: { name: string; data: unknown }) {
	const isThreadRunning = useAuiState(({ thread }) => thread.isRunning);
	const isLastMessage = useAuiState(({ message }) => message?.isLast ?? false);
	const isMessageStreaming = isThreadRunning && isLastMessage;
	const content = useAuiState(({ message }) => message?.content);

	const steps = useMemo<ThinkingStepInput[]>(
		() => (data as { steps: ThinkingStepInput[] } | null)?.steps ?? [],
		[data]
	);

	const items = useMemo(
		() => buildTimeline(steps, Array.isArray(content) ? content : undefined),
		[steps, content]
	);

	if (items.length === 0) return null;

	return (
		<div className="mb-3 -mx-2 leading-normal">
			<Timeline items={items} isThreadRunning={isMessageStreaming} />
		</div>
	);
}

/**
 * Drop-in replacement for the legacy ``ThinkingStepsDataUI``. Same
 * registration name (``thinking-steps``) so consumers (assistant-
 * message.tsx, public-thread.tsx, free-chat-page.tsx, etc.) just swap
 * the import — no SSE relay changes, no message format changes.
 */
export const TimelineDataUI = makeAssistantDataUI({
	name: "thinking-steps",
	render: TimelineDataRenderer,
});
