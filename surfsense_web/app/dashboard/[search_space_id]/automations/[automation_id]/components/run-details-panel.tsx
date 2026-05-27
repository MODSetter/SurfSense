"use client";
import { AlertCircle, FileOutput, GitCommitHorizontal, Package, Settings2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useAutomationRun } from "@/hooks/use-automation-runs";

interface RunDetailsPanelProps {
	automationId: number;
	runId: number;
}

/**
 * Expanded view of a single run. Fetches lazily — the parent only renders
 * this once the row is opened, so the list view stays cheap.
 *
 * We surface the four most actionable sections (error first when present,
 * then output, step results, artifacts, inputs). The full
 * ``definition_snapshot`` is omitted because it usually mirrors the live
 * definition — surfacing it would dominate the panel without informing
 * what the user is trying to learn ("did this work? what did it do?").
 */
export function RunDetailsPanel({ automationId, runId }: RunDetailsPanelProps) {
	const { data: run, isLoading, error } = useAutomationRun(automationId, runId);

	if (isLoading) {
		return (
			<div className="space-y-3 p-4 bg-muted/20 border-t border-border/60">
				<Skeleton className="h-3 w-32" />
				<Skeleton className="h-24 w-full" />
			</div>
		);
	}

	if (error || !run) {
		return (
			<div className="p-4 bg-muted/20 border-t border-border/60 text-xs text-muted-foreground">
				Couldn't load run details{error?.message ? `: ${error.message}` : "."}
			</div>
		);
	}

	const hasError = run.error && Object.keys(run.error).length > 0;
	const hasOutput = run.output && Object.keys(run.output).length > 0;
	const hasInputs = Object.keys(run.inputs ?? {}).length > 0;

	return (
		<div className="space-y-4 p-4 bg-muted/20 border-t border-border/60">
			{hasError && (
				<Section icon={AlertCircle} label="Error" tone="destructive">
					<JsonBlock value={run.error} />
				</Section>
			)}

			{hasOutput && (
				<Section icon={FileOutput} label="Output">
					<JsonBlock value={run.output} />
				</Section>
			)}

			<Section icon={GitCommitHorizontal} label={`Step results · ${run.step_results.length}`}>
				{run.step_results.length === 0 ? (
					<p className="text-xs text-muted-foreground">No steps recorded.</p>
				) : (
					<JsonBlock value={run.step_results} />
				)}
			</Section>

			{run.artifacts.length > 0 && (
				<Section icon={Package} label={`Artifacts · ${run.artifacts.length}`}>
					<JsonBlock value={run.artifacts} />
				</Section>
			)}

			{hasInputs && (
				<Section icon={Settings2} label="Resolved inputs">
					<JsonBlock value={run.inputs} />
				</Section>
			)}
		</div>
	);
}

function Section({
	icon: Icon,
	label,
	tone = "default",
	children,
}: {
	icon: typeof AlertCircle;
	label: string;
	tone?: "default" | "destructive";
	children: React.ReactNode;
}) {
	return (
		<div className="space-y-1.5">
			<div
				className={
					tone === "destructive"
						? "flex items-center gap-1.5 text-[11px] font-medium text-destructive uppercase tracking-wider"
						: "flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground uppercase tracking-wider"
				}
			>
				<Icon className="h-3 w-3" aria-hidden />
				{label}
			</div>
			{children}
		</div>
	);
}

function JsonBlock({ value }: { value: unknown }) {
	return (
		<pre className="rounded-md bg-background/60 px-3 py-2 text-[11px] font-mono text-foreground overflow-x-auto whitespace-pre-wrap break-words max-h-64">
			{JSON.stringify(value, null, 2)}
		</pre>
	);
}
