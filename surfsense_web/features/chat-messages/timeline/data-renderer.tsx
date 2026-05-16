"use client";

import { makeAssistantDataUI, useAuiState } from "@assistant-ui/react";
import { useMemo } from "react";
import { PendingInterruptProvider, usePendingInterrupt } from "@/features/chat-messages/hitl";
import { buildTimeline, type ThinkingStepInput } from "./build-timeline";
import { Timeline } from "./timeline";

const noopSubmit = () => {};

/**
 * assistant-ui data UI for the ``thinking-steps`` data-part.
 *
 * Re-scopes the global ``PendingInterruptProvider`` per message: approval
 * cards only mount under the assistant message that owns the interrupt
 * (otherwise every message in scrollback would render its own cards).
 */
function TimelineDataRenderer({ data }: { name: string; data: unknown }) {
	const isThreadRunning = useAuiState(({ thread }) => thread.isRunning);
	const isLastMessage = useAuiState(({ message }) => message?.isLast ?? false);
	const isMessageStreaming = isThreadRunning && isLastMessage;
	const content = useAuiState(({ message }) => message?.content);
	const messageId = useAuiState(({ message }) => message?.id);
	const pendingValue = usePendingInterrupt();
	const pendingForThisMessage = useMemo(
		() => (pendingValue?.pendingInterrupts ?? []).filter((p) => p.assistantMsgId === messageId),
		[pendingValue?.pendingInterrupts, messageId]
	);
	const onSubmit = pendingValue?.onSubmit ?? noopSubmit;

	const steps = useMemo<ThinkingStepInput[]>(
		() => (data as { steps: ThinkingStepInput[] } | null)?.steps ?? [],
		[data]
	);

	const items = useMemo(
		() => buildTimeline(steps, Array.isArray(content) ? content : undefined),
		[steps, content]
	);

	if (items.length === 0 && pendingForThisMessage.length === 0) return null;

	return (
		<div className="mb-3 -mx-2 leading-normal">
			<PendingInterruptProvider pendingInterrupts={pendingForThisMessage} onSubmit={onSubmit}>
				<Timeline items={items} isThreadRunning={isMessageStreaming} />
			</PendingInterruptProvider>
		</div>
	);
}

/** Registers under ``thinking-steps`` so consumers swap the import only. */
export const TimelineDataUI = makeAssistantDataUI({
	name: "thinking-steps",
	render: TimelineDataRenderer,
});
