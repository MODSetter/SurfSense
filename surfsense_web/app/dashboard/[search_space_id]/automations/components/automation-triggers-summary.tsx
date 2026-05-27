"use client";
import { CalendarClock, Pause } from "lucide-react";
import type { Trigger } from "@/contracts/types/automation.types";
import { describeCron } from "../lib/describe-cron";

interface AutomationTriggersSummaryProps {
	triggers: Trigger[];
}

/**
 * One-line summary of an automation's triggers for the list view.
 *
 * v1 only registers ``schedule`` so this stays compact:
 *   - 0 triggers → "No triggers"
 *   - 1 schedule trigger → "Mon–Fri at 09:00 · UTC" + disabled badge if off
 *   - >1 → "N triggers"
 *
 * The detail page renders the full per-trigger editor.
 */
export function AutomationTriggersSummary({ triggers }: AutomationTriggersSummaryProps) {
	if (triggers.length === 0) {
		return <span className="text-xs text-muted-foreground">No triggers</span>;
	}

	if (triggers.length > 1) {
		return <span className="text-xs text-muted-foreground">{triggers.length} triggers</span>;
	}

	const [trigger] = triggers;

	if (trigger.type === "schedule") {
		const cron = typeof trigger.params.cron === "string" ? trigger.params.cron : undefined;
		const tz = typeof trigger.params.timezone === "string" ? trigger.params.timezone : "UTC";
		const human = cron ? describeCron(cron) : "Schedule";

		return (
			<span className="inline-flex items-center gap-1.5 text-xs">
				<CalendarClock className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
				<span className="text-foreground">{human}</span>
				<span className="text-muted-foreground">· {tz}</span>
				{!trigger.enabled && (
					<span className="inline-flex items-center gap-1 rounded-md border border-border/60 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
						<Pause className="h-2.5 w-2.5" aria-hidden />
						Off
					</span>
				)}
			</span>
		);
	}

	return <span className="text-xs text-muted-foreground capitalize">{trigger.type}</span>;
}
