"use client";
import { CheckCircle2, ChevronDown, MinusCircle, XCircle } from "lucide-react";
import { memo, useState } from "react";
import { JsonView } from "@/components/json-view";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { RunStepResult } from "@/contracts/types/automation.types";
import { formatDuration } from "@/lib/automations/run-duration";
import { cn } from "@/lib/utils";

type BadgeVariant = React.ComponentProps<typeof Badge>["variant"];

const STATUS_BADGE: Record<
	string,
	{ label: string; variant: BadgeVariant; icon: typeof CheckCircle2 }
> = {
	succeeded: { label: "Succeeded", variant: "outline", icon: CheckCircle2 },
	failed: { label: "Failed", variant: "destructive", icon: XCircle },
	skipped: { label: "Skipped", variant: "secondary", icon: MinusCircle },
};

function StepStatusBadge({ status }: { status: string }) {
	const meta = STATUS_BADGE[status] ?? {
		label: status,
		variant: "outline" as const,
		icon: MinusCircle,
	};
	const Icon = meta.icon;
	return (
		<Badge variant={meta.variant} className="shrink-0">
			<Icon aria-hidden />
			{meta.label}
		</Badge>
	);
}

/**
 * One step from a run's ``step_results``. Surfaces the agent's markdown
 * ``final_message`` first-class (rendered, not raw), shows step errors as a
 * readable alert, and keeps the full structured payload behind a "View raw"
 * collapsible escape hatch.
 */
export const RunStepResultCard = memo(function RunStepResultCard({
	step,
}: {
	step: RunStepResult;
}) {
	const [rawOpen, setRawOpen] = useState(false);

	const duration = formatDuration(step.started_at, step.finished_at);
	const attempts = step.attempts ?? 0;
	const finalMessage =
		typeof step.result?.final_message === "string" ? step.result.final_message : null;
	const errorMessage = step.error?.message;
	const hasMeta = Boolean(duration) || attempts > 1;

	return (
		<Card className="border-border/60 shadow-none">
			<CardHeader className="gap-2 space-y-0 p-3">
				<div className="flex items-center justify-between gap-3">
					<div className="flex min-w-0 items-center gap-2">
						<span className="truncate font-mono text-xs font-medium">{step.action}</span>
						<span className="truncate text-xs text-muted-foreground">{step.step_id}</span>
					</div>
					<StepStatusBadge status={step.status} />
				</div>
				{hasMeta ? (
					<div className="flex items-center gap-3 text-[11px] text-muted-foreground tabular-nums">
						{duration ? <span>{duration}</span> : null}
						{attempts > 1 ? <span>{attempts} attempts</span> : null}
					</div>
				) : null}
			</CardHeader>

			<CardContent className="flex flex-col gap-3 p-3 pt-0">
				{errorMessage ? (
					<Alert variant="destructive">
						<XCircle aria-hidden />
						<AlertTitle>{step.error?.type ?? "Error"}</AlertTitle>
						<AlertDescription className="wrap-break-word">{errorMessage}</AlertDescription>
					</Alert>
				) : null}

				{finalMessage ? (
					<div className="min-w-0 wrap-break-word rounded-md border border-border/60 bg-background px-3 py-2">
						<MarkdownViewer content={finalMessage} />
					</div>
				) : null}

				<Collapsible open={rawOpen} onOpenChange={setRawOpen}>
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
							<JsonView src={step} collapsed={1} />
						</ScrollArea>
					</CollapsibleContent>
				</Collapsible>
			</CardContent>
		</Card>
	);
});
