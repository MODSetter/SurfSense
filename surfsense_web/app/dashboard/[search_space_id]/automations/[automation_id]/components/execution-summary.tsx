"use client";
import type { Execution } from "@/contracts/types/automation.types";

interface ExecutionSummaryProps {
	execution: Execution;
}

/**
 * Compact view of an automation's execution defaults (wall-clock cap,
 * retries, backoff, concurrency, on_failure presence). Per-step overrides
 * are shown inside each PlanStepCard, not here.
 */
export function ExecutionSummary({ execution }: ExecutionSummaryProps) {
	return (
		<dl className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2 text-xs">
			<Item label="Timeout" value={`${execution.timeout_seconds}s`} />
			<Item label="Max retries" value={String(execution.max_retries)} />
			<Item label="Retry backoff" value={execution.retry_backoff} />
			<Item label="Concurrency" value={execution.concurrency} />
			{execution.on_failure.length > 0 && (
				<Item
					label="On failure"
					value={`${execution.on_failure.length} step${execution.on_failure.length === 1 ? "" : "s"}`}
				/>
			)}
		</dl>
	);
}

function Item({ label, value }: { label: string; value: string }) {
	return (
		<div className="flex flex-col gap-0.5 min-w-0">
			<dt className="text-muted-foreground">{label}</dt>
			<dd className="text-foreground font-medium truncate">{value}</dd>
		</div>
	);
}
