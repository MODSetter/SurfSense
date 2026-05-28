"use client";
import { ArrowRightCircle, GitCommitHorizontal } from "lucide-react";
import type { PlanStep } from "@/contracts/types/automation.types";

interface PlanStepCardProps {
	step: PlanStep;
	index: number;
}

/**
 * Read-only view of one plan step. Renders the step_id + action prominently,
 * then a definition list of the per-step knobs, and finally the params as
 * formatted JSON. Editable mode is out of scope here — definition edits live
 * on the (future) raw-JSON path.
 */
export function PlanStepCard({ step, index }: PlanStepCardProps) {
	return (
		<div className="rounded-md border border-border/60 overflow-hidden">
			<div className="flex items-center gap-2 px-4 py-2 border-b border-border/60 bg-muted/30">
				<span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
					{index + 1}
				</span>
				<span className="text-sm font-medium text-foreground">{step.step_id}</span>
				<ArrowRightCircle className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
				<span className="text-xs font-mono text-muted-foreground">{step.action}</span>
			</div>

			<div className="px-4 py-3 space-y-3">
				{(step.when ||
					step.output_as ||
					step.max_retries != null ||
					step.timeout_seconds != null) && (
					<dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
						{step.when && (
							<DefRow label="When" value={<code className="font-mono">{step.when}</code>} />
						)}
						{step.output_as && (
							<DefRow
								label="Output as"
								value={<code className="font-mono">{step.output_as}</code>}
							/>
						)}
						{step.max_retries != null && (
							<DefRow label="Max retries" value={String(step.max_retries)} />
						)}
						{step.timeout_seconds != null && (
							<DefRow label="Timeout" value={`${step.timeout_seconds}s`} />
						)}
					</dl>
				)}

				<div>
					<div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground mb-1.5">
						<GitCommitHorizontal className="h-3.5 w-3.5" aria-hidden />
						Params
					</div>
					<pre className="rounded-md bg-muted/40 px-3 py-2 text-xs font-mono text-foreground overflow-x-auto whitespace-pre-wrap break-words">
						{JSON.stringify(step.params, null, 2)}
					</pre>
				</div>
			</div>
		</div>
	);
}

function DefRow({ label, value }: { label: string; value: React.ReactNode }) {
	return (
		<div className="flex items-baseline gap-2 min-w-0">
			<dt className="text-muted-foreground shrink-0">{label}:</dt>
			<dd className="text-foreground min-w-0 truncate">{value}</dd>
		</div>
	);
}
