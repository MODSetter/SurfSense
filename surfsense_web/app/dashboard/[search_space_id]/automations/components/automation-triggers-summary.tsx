"use client";
import { CalendarClock, Pause } from "lucide-react";
import type { Trigger } from "@/contracts/types/automation.types";

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

// ----------------------------------------------------------------------------
// Minimal cron describer for the common 5-field patterns SurfSense automations
// surface today. Falls back to the raw expression when unrecognized so the user
// still sees something honest instead of a guess.
//
// Kept inline (not a library) because:
//   - v1 only needs to recognize a small set of patterns produced by the
//     drafter LLM (hourly/daily/weekdays/weekly/monthly).
//   - All current consumers live in this slice. If reuse grows, lift to
//     ``lib/cron-describe.ts``.
// ----------------------------------------------------------------------------

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function describeCron(cron: string): string {
	const parts = cron.trim().split(/\s+/);
	if (parts.length !== 5) return cron;

	const [minute, hour, dom, month, dow] = parts;

	// Daily at H:MM (matches the very common "0 9 * * *")
	if (month === "*" && dom === "*" && dow === "*" && /^\d+$/.test(minute) && /^\d+$/.test(hour)) {
		return `Daily at ${formatTime(hour, minute)}`;
	}

	// Weekdays at H:MM ("0 9 * * 1-5")
	if (month === "*" && dom === "*" && dow === "1-5" && /^\d+$/.test(minute) && /^\d+$/.test(hour)) {
		return `Mon–Fri at ${formatTime(hour, minute)}`;
	}

	// Specific weekday(s) ("0 9 * * 1" or "0 9 * * 1,3,5")
	if (
		month === "*" &&
		dom === "*" &&
		/^\d+$/.test(minute) &&
		/^\d+$/.test(hour) &&
		/^[\d,]+$/.test(dow)
	) {
		const days = dow
			.split(",")
			.map((d) => DAY_NAMES[Number(d) % 7])
			.filter(Boolean)
			.join(", ");
		if (days) return `${days} at ${formatTime(hour, minute)}`;
	}

	// Monthly on day N ("0 9 1 * *")
	if (
		month === "*" &&
		dow === "*" &&
		/^\d+$/.test(dom) &&
		/^\d+$/.test(hour) &&
		/^\d+$/.test(minute)
	) {
		return `Day ${dom} of each month at ${formatTime(hour, minute)}`;
	}

	// Hourly ("0 * * * *")
	if (month === "*" && dom === "*" && dow === "*" && hour === "*" && /^\d+$/.test(minute)) {
		return minute === "0" ? "Every hour" : `Every hour at :${minute.padStart(2, "0")}`;
	}

	return cron;
}

function formatTime(hour: string, minute: string): string {
	return `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
}
