"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { ElapsedTime, projectElapsed } from "@/components/prompt-kit/elapsed-time";
import type { ActivityTimingData, ActivityTimingProjection } from "@/lib/chat/activity-journal";
import { trackActivityTimingContractViolation } from "@/lib/posthog/events";
import {
	resolveTurnTimingDisplay,
	type TimingSnapshot,
	type TurnTimingDisplay,
} from "./turn-timing-state";

interface AssistantTurnTimingStateProps {
	messageId: string;
	timing: ActivityTimingData | null;
	projection: ActivityTimingProjection | null;
	threadRunning: boolean;
}

export function useAssistantTurnTiming({
	messageId,
	timing,
	projection,
	threadRunning,
}: AssistantTurnTimingStateProps): TurnTimingDisplay {
	const [retained, setRetained] = useState<TimingSnapshot | null>(() =>
		timing ? { timing, projection: timing.status === "running" ? projection : null } : null
	);
	const current = useMemo(
		() =>
			timing ? { timing, projection: timing.status === "running" ? projection : null } : retained,
		[timing, projection, retained]
	);
	const [frozenDurationMs, setFrozenDurationMs] = useState<number>();
	const reportedMissingTerminal = useRef(false);

	useEffect(() => {
		if (!timing) return;
		setRetained({
			timing,
			projection: timing.status === "running" ? projection : null,
		});
	}, [timing, projection]);

	useEffect(() => {
		if (!current || current.timing.status !== "running" || threadRunning) {
			setFrozenDurationMs(undefined);
			return;
		}
		setFrozenDurationMs(
			(value) => value ?? projectElapsed(current.timing, current.projection ?? undefined)
		);
		if (!reportedMissingTerminal.current) {
			reportedMissingTerminal.current = true;
			trackActivityTimingContractViolation(messageId, current.timing.activeDurationMs);
		}
	}, [current, messageId, threadRunning]);

	return resolveTurnTimingDisplay(current, threadRunning, frozenDurationMs);
}

export function AssistantTurnTiming({ display }: { display: TurnTimingDisplay }) {
	if (display.phase === "placeholder") return null;

	return (
		<span className="contents" data-testid="assistant-turn-timing">
			<ElapsedTime timing={display.timing} projection={display.projection} />
		</span>
	);
}
