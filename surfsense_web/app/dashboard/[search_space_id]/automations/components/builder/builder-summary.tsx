"use client";
import { Dot } from "lucide-react";
import { type BuilderForm, scheduleToCron } from "@/lib/automations/builder-schema";
import { describeCron } from "@/lib/automations/describe-cron";

interface BuilderSummaryProps {
	form: BuilderForm;
}

/**
 * Live, read-only mirror of what will be created. Mirrors the layout of the
 * chat ``AutomationDraftPreview`` so the two creation paths feel consistent.
 */
export function BuilderSummary({ form }: BuilderSummaryProps) {
	const automationName = form.name.trim() || "Untitled automation";
	const scheduleDescription = form.schedule ? describeCron(scheduleToCron(form.schedule)) : null;
	const taskCountLabel = `${form.tasks.length} task${form.tasks.length === 1 ? "" : "s"}`;
	const visibleTasks = form.tasks.slice(0, 2);
	const hiddenTaskCount = form.tasks.length - visibleTasks.length;

	return (
		<div className="flex flex-col gap-4 text-sm">
			<div className="flex flex-col gap-1">
				<p className="truncate text-sm font-semibold text-muted-foreground" title={automationName}>
					{automationName}
				</p>
			</div>

			<div className="h-px bg-border/60" />

			<div className="flex flex-col gap-3">
				<SummaryRow label="Schedule">
					{scheduleDescription ? (
						<span className="flex flex-wrap items-center gap-x-1 gap-y-0.5">
							<span>{scheduleDescription}</span>
							<Dot className="size-4 text-muted-foreground" aria-hidden />
							<span>{form.timezone}</span>
						</span>
					) : (
						<span>No schedule — won't run automatically</span>
					)}
				</SummaryRow>

				<SummaryRow label={taskCountLabel}>
					<ol className="ml-4 space-y-1">
						{visibleTasks.map((task, index) => (
							<li key={task.id} className="flex gap-2">
								<span className="shrink-0 text-muted-foreground">{index + 1}.</span>
								<span className="line-clamp-1 min-w-0">
									{task.query.trim() || "No instructions yet"}
								</span>
							</li>
						))}
						{hiddenTaskCount > 0 && (
							<li className="text-muted-foreground">+{hiddenTaskCount} more tasks</li>
						)}
					</ol>
				</SummaryRow>

				<SummaryRow label="Approvals">
					{form.unattended ? "Runs without approval prompts" : "Approval prompts are rejected"}
				</SummaryRow>
			</div>
		</div>
	);
}

function SummaryRow({
	label,
	children,
}: {
	label: string;
	children: React.ReactNode;
}) {
	return (
		<div className="flex flex-col gap-1 text-xs">
			<div className="font-medium text-muted-foreground">{label}</div>
			<div className="text-foreground">{children}</div>
		</div>
	);
}
