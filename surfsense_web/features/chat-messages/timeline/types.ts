import type { ActivityStatus } from "@/lib/chat/activity-journal";

/** Result-card status also admits assistant-ui's pre-start state. */
export type ItemStatus = ActivityStatus | "pending";
