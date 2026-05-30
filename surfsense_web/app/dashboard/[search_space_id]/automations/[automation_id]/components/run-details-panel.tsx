"use client";
import {
	AlertCircle,
	ChevronDown,
	FileOutput,
	GitCommitHorizontal,
	Package,
	Settings2,
} from "lucide-react";
import { useState } from "react";
import { JsonView } from "@/components/json-view";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import type { RunStepResult } from "@/contracts/types/automation.types";
import { useAutomationRun } from "@/hooks/use-automation-runs";
import { cn } from "@/lib/utils";
import { RunStepResultCard } from "./run-step-result-card";

interface RunDetailsPanelProps {
	automationId: number;
	runId: number;
}

/**
 * Expanded view of a single run. Fetches lazily — the parent only renders
 * this once the row is opened, so the list view stays cheap.
 *
 * We surface the run outcome readably: a run-level error first (when
 * present), then per-step cards that render the agent's markdown
 * ``final_message`` directly, and finally the structural artifacts/inputs.
 * The full ``definition_snapshot`` is omitted because it usually mirrors the
 * live definition — surfacing it would dominate the panel without informing
 * what the user is trying to learn ("did this work? what did it do?").
 */
export function RunDetailsPanel({ automationId, runId }: RunDetailsPanelProps) {
	const { data: run, isLoading, error } = useAutomationRun(automationId, runId);

	if (isLoading) {
		return (
			<div className="flex flex-col gap-3 border-t border-border/60 bg-muted/20 p-4">
				<Skeleton className="h-3 w-32" />
				<Skeleton className="h-24 w-full" />
			</div>
		);
	}

	if (error || !run) {
		return (
			<div className="border-t border-border/60 bg-muted/20 p-4 text-xs text-muted-foreground">
				Couldn't load run details{error?.message ? `: ${error.message}` : "."}
			</div>
		);
	}

	const runError = run.error && Object.keys(run.error).length > 0 ? run.error : null;
	const hasOutput = run.output && Object.keys(run.output).length > 0;
	const hasInputs = Object.keys(run.inputs ?? {}).length > 0;
	const steps = run.step_results as RunStepResult[];
	const hasDiagnostics = run.artifacts.length > 0 || hasInputs;

	return (
		<div className="flex flex-col gap-4 border-t border-border/60 bg-muted/20 p-4">
			{runError ? <RunErrorSection error={runError} /> : null}

			{hasOutput ? (
				<Section icon={FileOutput} label="Output">
					<JsonBlock value={run.output} />
				</Section>
			) : null}

			<Section icon={GitCommitHorizontal} label={`Step results · ${steps.length}`}>
				{steps.length === 0 ? (
					<p className="text-xs text-muted-foreground">No steps recorded.</p>
				) : (
					<div className="flex flex-col gap-2">
						{steps.map((step, index) => (
							<RunStepResultCard key={step.step_id ?? index} step={step} />
						))}
					</div>
				)}
			</Section>

			{hasDiagnostics ? <Separator className="bg-border/60" /> : null}

			{run.artifacts.length > 0 ? (
				<Section icon={Package} label={`Artifacts · ${run.artifacts.length}`}>
					<JsonBlock value={run.artifacts} />
				</Section>
			) : null}

			{hasInputs ? (
				<Section icon={Settings2} label="Resolved inputs">
					<JsonBlock value={run.inputs} />
				</Section>
			) : null}
		</div>
	);
}

/**
 * Run-level error: a readable destructive alert when a message is present,
 * with the full structured error available behind a raw toggle.
 */
function RunErrorSection({ error }: { error: Record<string, unknown> }) {
	const [rawOpen, setRawOpen] = useState(false);
	const message = typeof error.message === "string" ? error.message : null;
	const type = typeof error.type === "string" ? error.type : "Run failed";

	return (
		<Section icon={AlertCircle} label="Error" tone="destructive">
			{message ? (
				<Alert variant="destructive">
					<AlertCircle aria-hidden />
					<AlertTitle>{type}</AlertTitle>
					<AlertDescription className="wrap-break-word">{message}</AlertDescription>
				</Alert>
			) : null}
			<Collapsible open={rawOpen} onOpenChange={setRawOpen} className="mt-2">
				<CollapsibleTrigger asChild>
					<Button
						type="button"
						variant="ghost"
						size="sm"
						className="h-7 w-fit px-2 text-xs text-muted-foreground"
						aria-expanded={rawOpen}
					>
						<ChevronDown
							className={cn(
								"transition-transform motion-reduce:transition-none",
								rawOpen && "rotate-180"
							)}
							aria-hidden
						/>
						{rawOpen ? "Hide raw" : "View raw"}
					</Button>
				</CollapsibleTrigger>
				<CollapsibleContent>
					<ScrollArea className="mt-2 max-h-64 rounded-md bg-muted/40 px-3 py-2">
						<JsonView src={error} collapsed={1} />
					</ScrollArea>
				</CollapsibleContent>
			</Collapsible>
		</Section>
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
		<div className="flex flex-col gap-1.5">
			<div
				className={cn(
					"flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider",
					tone === "destructive" ? "text-destructive" : "text-muted-foreground"
				)}
			>
				<Icon className="size-3" aria-hidden />
				{label}
			</div>
			{children}
		</div>
	);
}

function JsonBlock({ value }: { value: unknown }) {
	return (
		<ScrollArea className="max-h-64 rounded-md bg-muted/40 px-3 py-2">
			<JsonView src={value} collapsed={1} />
		</ScrollArea>
	);
}
