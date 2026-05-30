"use client";
import { ChevronDown, ChevronRight, Hand } from "lucide-react";
import { useState } from "react";
import type { RunSummary } from "@/contracts/types/automation.types";
import { formatDuration } from "@/lib/automations/run-duration";
import { formatRelativeDate } from "@/lib/format-date";
import { RunDetailsPanel } from "./run-details-panel";
import { RunStatusBadge } from "./run-status-badge";

interface RunRowProps {
	run: RunSummary;
	automationId: number;
}

/**
 * One run row. Click to expand → fetches the full run and shows the
 * details panel inline. State is local to each row so multiple panels
 * can be open at once (or none).
 */
export function RunRow({ run, automationId }: RunRowProps) {
	const [open, setOpen] = useState(false);
	const duration = formatDuration(run.started_at, run.finished_at);
	const startedLabel = run.started_at
		? formatRelativeDate(run.started_at)
		: formatRelativeDate(run.created_at);

	return (
		<div className="rounded-md border border-border/60 overflow-hidden">
			<button
				type="button"
				onClick={() => setOpen((value) => !value)}
				className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left hover:bg-muted/30 transition-colors"
				aria-expanded={open}
			>
				<div className="flex items-center gap-3 min-w-0">
					{open ? (
						<ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden />
					) : (
						<ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden />
					)}
					<RunStatusBadge status={run.status} />
					<span className="text-xs text-muted-foreground truncate">{startedLabel}</span>
				</div>
				<div className="flex items-center gap-3 shrink-0 text-xs text-muted-foreground">
					{duration && <span className="font-mono">{duration}</span>}
					<TriggerSource triggerId={run.trigger_id ?? null} />
				</div>
			</button>

			{open && <RunDetailsPanel automationId={automationId} runId={run.id} />}
		</div>
	);
}

function TriggerSource({ triggerId }: { triggerId: number | null }) {
	if (triggerId == null) {
		return (
			<span className="inline-flex items-center gap-1">
				<Hand className="h-3 w-3" aria-hidden />
				Manual
			</span>
		);
	}
	return <span>via trigger #{triggerId}</span>;
}
