"use client";
import { CalendarClock, CheckCircle2, ListOrdered, type LucideIcon, XCircle } from "lucide-react";
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
	const scheduleLabel = form.schedule
		? `${describeCron(scheduleToCron(form.schedule))} · ${form.timezone}`
		: "No schedule — won't run automatically";

	return (
		<div className="space-y-4 text-sm">
			<div className="space-y-1">
				<p className="font-medium text-foreground">{form.name.trim() || "Untitled automation"}</p>
				{form.description?.trim() && (
					<p className="text-xs text-muted-foreground">{form.description.trim()}</p>
				)}
			</div>

			<Section icon={CalendarClock} label="Schedule">
				<p className="text-xs text-foreground">{scheduleLabel}</p>
			</Section>

			<Section
				icon={ListOrdered}
				label={`Tasks · ${form.tasks.length} step${form.tasks.length === 1 ? "" : "s"}`}
			>
				<ol className="space-y-1.5 text-xs">
					{form.tasks.map((task, index) => (
						<li key={task.id} className="flex items-start gap-2">
							<span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-muted text-[10px] font-medium text-muted-foreground shrink-0 mt-0.5">
								{index + 1}
							</span>
							<span className="min-w-0 flex-1 space-y-1">
								<span className="block text-foreground line-clamp-2">
									{task.query.trim() || (
										<span className="text-muted-foreground">No instructions yet</span>
									)}
								</span>
								{task.mentions.length > 0 && (
									<span className="flex flex-wrap gap-1">
										{task.mentions.map((mention) => (
											<span
												key={`${mention.kind}:${mention.id}`}
												className="inline-flex max-w-[140px] items-center truncate rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary/70"
											>
												@{mention.title}
											</span>
										))}
									</span>
								)}
							</span>
						</li>
					))}
				</ol>
			</Section>

			<div className="flex items-center gap-1.5 text-xs text-muted-foreground">
				{form.unattended ? (
					<CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" aria-hidden />
				) : (
					<XCircle className="h-3.5 w-3.5" aria-hidden />
				)}
				{form.unattended ? "Runs without approval prompts" : "Will reject approval prompts"}
			</div>
		</div>
	);
}

function Section({
	icon: Icon,
	label,
	children,
}: {
	icon: LucideIcon;
	label: string;
	children: React.ReactNode;
}) {
	return (
		<div className="space-y-1.5">
			<div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
				<Icon className="h-3 w-3" aria-hidden />
				{label}
			</div>
			{children}
		</div>
	);
}
