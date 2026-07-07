"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";
import type { ScraperRunEvent } from "@/contracts/types/scraper.types";
import { formatDuration } from "@/lib/playground/format";

/** One-line human label for a progress/lifecycle event. */
function eventLabel(event: ScraperRunEvent): string {
	const base =
		event.message ||
		(event.phase ? event.phase.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "Working");
	if (event.current !== undefined && event.current !== null) {
		const counter =
			event.total !== undefined && event.total !== null
				? `${event.current}/${event.total}`
				: String(event.current);
		return `${base} (${counter})`;
	}
	return base;
}

/**
 * Live progress for an in-flight async run: a headline status, a determinate
 * bar when counts are known, a running elapsed timer, and a scrolling event log.
 */
export function RunProgressPanel({
	latest,
	events,
	elapsedMs,
}: {
	latest: ScraperRunEvent | null;
	events: ScraperRunEvent[];
	elapsedMs: number;
}) {
	const logRef = useRef<HTMLDivElement>(null);

	// Keep the newest line in view as the log grows.
	useEffect(() => {
		const el = logRef.current;
		if (el) el.scrollTop = el.scrollHeight;
	}, [events.length]);

	const total = latest?.total ?? undefined;
	const current = latest?.current ?? undefined;
	const pct =
		typeof current === "number" && typeof total === "number" && total > 0
			? Math.min(100, Math.round((current / total) * 100))
			: null;

	return (
		<div className="space-y-3 rounded-md border border-border/60 p-4">
			<div className="flex items-center justify-between gap-3">
				<div className="flex min-w-0 items-center gap-2">
					<Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
					<span className="truncate text-sm font-medium">
						{latest ? eventLabel(latest) : "Starting…"}
					</span>
				</div>
				<span className="shrink-0 text-xs tabular-nums text-muted-foreground">
					{formatDuration(elapsedMs)}
				</span>
			</div>

			{pct !== null && (
				<div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
					<div
						className="h-full rounded-full bg-primary transition-all duration-300"
						style={{ width: `${pct}%` }}
					/>
				</div>
			)}

			{events.length > 0 && (
				<div
					ref={logRef}
					className="max-h-56 space-y-1 overflow-y-auto rounded border border-border/40 bg-muted/20 p-2 font-mono text-xs text-muted-foreground"
				>
					{events.map((event, i) => (
						<div key={`${event.ts ?? i}-${i}`} className="truncate">
							{eventLabel(event)}
						</div>
					))}
				</div>
			)}
		</div>
	);
}
