"use client";

import { memo, useEffect, useState } from "react";

import type { ActivityTimingData } from "@/lib/chat/streaming-state";

export function formatElapsed(milliseconds: number): string {
	const seconds = Math.max(0, milliseconds) / 1000;
	if (seconds < 60) return `${seconds.toFixed(1)}s`;
	return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(1)}s`;
}

export function projectElapsed(timing: ActivityTimingData, nowMs = Date.now()): number {
	if (timing.status !== "running" || !timing.sampledAt) return timing.activeDurationMs;
	return timing.activeDurationMs + Math.max(0, nowMs - Date.parse(timing.sampledAt));
}

export const ElapsedTime = memo(function ElapsedTime({ timing }: { timing: ActivityTimingData }) {
	const [elapsed, setElapsed] = useState(() => projectElapsed(timing));

	useEffect(() => {
		setElapsed(projectElapsed(timing));
		if (timing.status !== "running" || !timing.sampledAt) return;
		const timer = window.setInterval(() => setElapsed(projectElapsed(timing)), 100);
		return () => window.clearInterval(timer);
	}, [timing]);

	return (
		<span className="shrink-0 font-mono text-[12px] text-muted-foreground/75 tabular-nums">
			{formatElapsed(elapsed)}
		</span>
	);
});
