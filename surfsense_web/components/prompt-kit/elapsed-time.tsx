"use client";

import { memo, useEffect, useState } from "react";

import type { ActivityTimingData, ActivityTimingProjection } from "@/lib/chat/streaming-state";

export function formatElapsed(milliseconds: number): string {
	const seconds = Math.max(0, milliseconds) / 1000;
	if (seconds < 60) return `${seconds.toFixed(1)}s`;
	return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(1)}s`;
}

export function projectElapsed(
	timing: ActivityTimingData,
	projection: ActivityTimingProjection | undefined,
	nowPerformanceMs = performance.now()
): number {
	if (
		timing.status !== "running" ||
		!projection ||
		projection.baseDurationMs !== timing.activeDurationMs
	) {
		return timing.activeDurationMs;
	}
	return (
		projection.baseDurationMs + Math.max(0, nowPerformanceMs - projection.receivedAtPerformanceMs)
	);
}

export const ElapsedTime = memo(function ElapsedTime({
	timing,
	projection,
}: {
	timing: ActivityTimingData;
	projection?: ActivityTimingProjection;
}) {
	const [elapsed, setElapsed] = useState(() => projectElapsed(timing, projection));

	useEffect(() => {
		setElapsed(projectElapsed(timing, projection));
		if (timing.status !== "running" || !projection) return;
		const timer = window.setInterval(() => setElapsed(projectElapsed(timing, projection)), 100);
		return () => window.clearInterval(timer);
	}, [timing, projection]);

	return (
		<span className="shrink-0 font-mono text-[12px] text-muted-foreground/75 tabular-nums">
			{formatElapsed(elapsed)}
		</span>
	);
});
