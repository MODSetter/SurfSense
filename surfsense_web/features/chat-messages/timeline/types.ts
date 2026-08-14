import type { ActivityStatus } from "@/lib/chat/streaming-state";

/** Result-card status also admits assistant-ui's pre-start state. */
export type ItemStatus = ActivityStatus | "pending";
