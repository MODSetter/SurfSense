import type { ActivityStatus } from "@/lib/chat/streaming-state";

/** Result-card status also admits assistant-ui's pre-start state. */
export type ItemStatus = ActivityStatus | "pending";

export interface VisibleReasoningBlock {
	id: string;
	text: string;
	status: "running" | "completed" | "interrupted";
	startedAt?: string;
	completedAt?: string;
}
