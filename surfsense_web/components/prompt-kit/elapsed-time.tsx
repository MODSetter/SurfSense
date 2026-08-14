"use client";

import { memo, useEffect, useState } from "react";

export function formatElapsed(milliseconds: number): string {
	const seconds = Math.max(0, milliseconds) / 1000;
	if (seconds < 60) return `${seconds.toFixed(1)}s`;
	return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(1)}s`;
}

export const ElapsedTime = memo(function ElapsedTime({
	startedAt,
	completedAt,
	running = !completedAt,
}: {
	startedAt: string | Date;
	completedAt?: string | Date;
	running?: boolean;
}) {
	const start = new Date(startedAt).getTime();
	const end = completedAt ? new Date(completedAt).getTime() : undefined;
	const [now, setNow] = useState(() => end ?? Date.now());

	useEffect(() => {
		if (end !== undefined) {
			setNow(end);
			return;
		}
		if (!running) return;
		const timer = window.setInterval(() => setNow(Date.now()), 100);
		return () => window.clearInterval(timer);
	}, [end, running]);

	if (!Number.isFinite(start) || (!running && end === undefined)) return null;
	return (
		<span className="shrink-0 font-mono text-[12px] text-muted-foreground tabular-nums">
			{formatElapsed(now - start)}
		</span>
	);
});
