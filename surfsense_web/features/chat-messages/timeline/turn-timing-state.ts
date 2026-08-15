import { projectElapsed } from "@/components/prompt-kit/elapsed-time";
import type { ActivityTimingData, ActivityTimingProjection } from "@/lib/chat/activity-journal";

export interface TimingSnapshot {
	timing: ActivityTimingData;
	projection: ActivityTimingProjection | null;
}

export type TurnTimingDisplay =
	| { phase: "placeholder" }
	| {
			phase: "live" | "static" | "frozen";
			timing: ActivityTimingData;
			projection?: ActivityTimingProjection;
	  };

export function resolveTurnTimingDisplay(
	snapshot: TimingSnapshot | null,
	threadRunning: boolean,
	frozenDurationMs?: number
): TurnTimingDisplay {
	if (!snapshot) return { phase: "placeholder" };
	if (snapshot.timing.status !== "running") {
		return { phase: "static", timing: snapshot.timing };
	}
	if (threadRunning) {
		return {
			phase: "live",
			timing: snapshot.timing,
			...(snapshot.projection ? { projection: snapshot.projection } : {}),
		};
	}
	return {
		phase: "frozen",
		timing: {
			status: "completed",
			activeDurationMs:
				frozenDurationMs ?? projectElapsed(snapshot.timing, snapshot.projection ?? undefined),
		},
	};
}
