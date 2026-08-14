"use client";

import { memo, useEffect, useState } from "react";

export function formatElapsed(milliseconds: number): string {
	const seconds = Math.max(0, milliseconds) / 1000;
	if (seconds < 60) return `${seconds.toFixed(1)}s`;
	return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(1)}s`;
}

export function projectElapsed(
	activeDurationMs: number,
	running: boolean,
	monotonicDeltaMs: number
): number {
	return activeDurationMs + (running ? Math.max(0, monotonicDeltaMs) : 0);
}

export const ElapsedTime = memo(function ElapsedTime({
	activeDurationMs,
	running,
}: {
	activeDurationMs: number;
	running: boolean;
}) {
	const [elapsed, setElapsed] = useState(activeDurationMs);

	useEffect(() => {
		if (!running) return;
		const started = performance.now();
		const timer = window.setInterval(
			() => setElapsed(projectElapsed(activeDurationMs, true, performance.now() - started)),
			100
		);
		return () => window.clearInterval(timer);
	}, [activeDurationMs, running]);

	return (
		<span className="shrink-0 font-mono text-[12px] text-muted-foreground/75 tabular-nums">
			{formatElapsed(elapsed)}
		</span>
	);
});
