/**
 * Minimal cron describer for the 5-field patterns the SurfSense drafter LLM
 * actually produces (daily, weekdays, weekly, monthly, hourly). Falls back
 * to the raw expression when unrecognized so the user still sees something
 * honest instead of a guess.
 *
 * Lives under ``lib/automations/`` because both the dashboard slice and the
 * chat ``create_automation`` approval card render schedule descriptions —
 * keeping the helper outside either feature avoids a layering violation.
 */

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function describeCron(cron: string): string {
	const parts = cron.trim().split(/\s+/);
	if (parts.length !== 5) return cron;

	const [minute, hour, dom, month, dow] = parts;

	// Daily at H:MM ("0 9 * * *")
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
