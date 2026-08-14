"use client";

import { useAuiState } from "@assistant-ui/react";
import { useMemo } from "react";
import { PendingInterruptProvider, usePendingInterrupt } from "@/features/chat-messages/hitl";
import { buildTimeline, type ThinkingStepInput } from "./build-timeline";
import { buildSemanticActivities } from "./semantic-activities";
import { Timeline } from "./timeline";
import type { VisibleReasoningBlock } from "./types";

const noopSubmit = () => {};

function extractSteps(content: readonly unknown[]): ThinkingStepInput[] {
	const part = content.find(
		(
			candidate
		): candidate is { type: "data-thinking-steps"; data: { steps?: ThinkingStepInput[] } } =>
			typeof candidate === "object" &&
			candidate !== null &&
			(candidate as { type?: unknown }).type === "data-thinking-steps"
	);
	return Array.isArray(part?.data?.steps) ? part.data.steps : [];
}

function extractReasoning(content: readonly unknown[]): VisibleReasoningBlock[] {
	let legacyIndex = 0;
	return content.flatMap((candidate) => {
		if (
			typeof candidate !== "object" ||
			candidate === null ||
			(candidate as { type?: unknown }).type !== "reasoning"
		) {
			return [];
		}
		const reasoning = candidate as {
			id?: unknown;
			text?: unknown;
			status?: unknown;
			startedAt?: unknown;
			completedAt?: unknown;
		};
		if (typeof reasoning.text !== "string" || reasoning.text.length === 0) return [];
		legacyIndex += 1;
		return [
			{
				id:
					typeof reasoning.id === "string" && reasoning.id
						? reasoning.id
						: `legacy-reasoning-${legacyIndex}`,
				text: reasoning.text,
				status:
					reasoning.status === "running" || reasoning.status === "interrupted"
						? reasoning.status
						: "completed",
				startedAt: typeof reasoning.startedAt === "string" ? reasoning.startedAt : undefined,
				completedAt: typeof reasoning.completedAt === "string" ? reasoning.completedAt : undefined,
			},
		];
	});
}

function hasAnswerText(content: readonly unknown[]): boolean {
	return content.some(
		(part) =>
			typeof part === "object" &&
			part !== null &&
			(part as { type?: unknown }).type === "text" &&
			typeof (part as { text?: unknown }).text === "string" &&
			(part as { text: string }).text.trim().length > 0
	);
}

export function TurnActivity({ showReasoning = true }: { showReasoning?: boolean }) {
	const isThreadRunning = useAuiState(({ thread }) => thread.isRunning);
	const isLastMessage = useAuiState(({ message }) => message?.isLast ?? false);
	const messageId = useAuiState(({ message }) => message?.id);
	const content = useAuiState(({ message }) => message?.content);
	const createdAt = useAuiState(({ message }) => message?.createdAt);
	const metadata = useAuiState(({ message }) => message?.metadata);
	const pendingValue = usePendingInterrupt();
	const isMessageStreaming = isThreadRunning && isLastMessage;
	const parts = Array.isArray(content) ? content : [];

	const items = useMemo(
		() =>
			buildSemanticActivities(
				buildTimeline(extractSteps(parts), parts).filter((item) => item.kind === "tool-call")
			),
		[parts]
	);
	const reasoning = useMemo(
		() => (showReasoning ? extractReasoning(parts) : []),
		[parts, showReasoning]
	);
	const pendingForMessage = useMemo(
		() =>
			(pendingValue?.pendingInterrupts ?? []).filter((item) => item.assistantMsgId === messageId),
		[pendingValue?.pendingInterrupts, messageId]
	);
	const custom = (metadata?.custom ?? {}) as Record<string, unknown>;
	const startedAt =
		(typeof custom.turnStartedAt === "string" ? custom.turnStartedAt : undefined) ??
		(createdAt instanceof Date ? createdAt.toISOString() : new Date().toISOString());

	return (
		<PendingInterruptProvider
			pendingInterrupts={pendingForMessage}
			onSubmit={pendingValue?.onSubmit ?? noopSubmit}
		>
			<Timeline
				items={items}
				reasoning={reasoning}
				isThreadRunning={isMessageStreaming}
				hasAnswer={hasAnswerText(parts)}
				startedAt={startedAt}
			/>
		</PendingInterruptProvider>
	);
}
