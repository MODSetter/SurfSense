/**
 * Bidirectional bridge between a friendly schedule model and the 5-field cron
 * expression the backend ``schedule`` trigger expects (see
 * ``app/automations/triggers/schedule/params.py``).
 *
 * The form builder never asks users to type cron. They pick a frequency + time
 * (+ days), which ``toCron`` compiles. On edit we ``fromCron`` an existing
 * expression back into the model; anything we don't recognize returns ``null``
 * so the caller can fall back to a raw-cron escape hatch instead of silently
 * losing the user's schedule.
 *
 * The recognized patterns are intentionally the same family that
 * ``describe-cron.ts`` humanizes, keeping the picker and the label in sync.
 */

export type ScheduleFrequency = "hourly" | "daily" | "weekdays" | "weekly" | "monthly";

export interface ScheduleModel {
	frequency: ScheduleFrequency;
	/** 0-23. Ignored for ``hourly``. */
	hour: number;
	/** 0-59. */
	minute: number;
	/** 0 (Sun) - 6 (Sat). Used by ``weekly``. */
	daysOfWeek: number[];
	/** 1-31. Used by ``monthly``. */
	dayOfMonth: number;
}

/** Sunday-first, matching cron's 0-6 day-of-week numbering. */
export const WEEKDAY_OPTIONS: ReadonlyArray<{ value: number; short: string; long: string }> = [
	{ value: 1, short: "Mon", long: "Monday" },
	{ value: 2, short: "Tue", long: "Tuesday" },
	{ value: 3, short: "Wed", long: "Wednesday" },
	{ value: 4, short: "Thu", long: "Thursday" },
	{ value: 5, short: "Fri", long: "Friday" },
	{ value: 6, short: "Sat", long: "Saturday" },
	{ value: 0, short: "Sun", long: "Sunday" },
];

export const FREQUENCY_OPTIONS: ReadonlyArray<{ value: ScheduleFrequency; label: string }> = [
	{ value: "hourly", label: "Every hour" },
	{ value: "daily", label: "Every day" },
	{ value: "weekdays", label: "Every weekday (Mon\u2013Fri)" },
	{ value: "weekly", label: "Specific days of the week" },
	{ value: "monthly", label: "Once a month" },
];

export const DEFAULT_SCHEDULE: ScheduleModel = {
	frequency: "weekdays",
	hour: 9,
	minute: 0,
	daysOfWeek: [1],
	dayOfMonth: 1,
};

function isInt(value: string): boolean {
	return /^\d+$/.test(value);
}

function clamp(value: number, min: number, max: number): number {
	if (Number.isNaN(value)) return min;
	return Math.min(max, Math.max(min, value));
}

/** Compile a schedule model into a 5-field cron expression. */
export function toCron(model: ScheduleModel): string {
	const minute = clamp(model.minute, 0, 59);
	const hour = clamp(model.hour, 0, 23);

	switch (model.frequency) {
		case "hourly":
			return `${minute} * * * *`;
		case "daily":
			return `${minute} ${hour} * * *`;
		case "weekdays":
			return `${minute} ${hour} * * 1-5`;
		case "weekly": {
			const days = [...new Set(model.daysOfWeek)].sort((a, b) => a - b);
			// Guard against an empty selection producing an invalid cron.
			const dow = days.length > 0 ? days.join(",") : "1";
			return `${minute} ${hour} * * ${dow}`;
		}
		case "monthly":
			return `${minute} ${hour} ${clamp(model.dayOfMonth, 1, 31)} * *`;
	}
}

/**
 * Parse a 5-field cron expression back into a schedule model. Returns ``null``
 * for anything outside the recognized pattern family so callers can fall back
 * to the raw-cron field.
 */
export function fromCron(cron: string): ScheduleModel | null {
	const parts = cron.trim().split(/\s+/);
	if (parts.length !== 5) return null;

	const [minute, hour, dom, month, dow] = parts;

	// Hourly: "M * * * *"
	if (month === "*" && dom === "*" && dow === "*" && hour === "*" && isInt(minute)) {
		return { ...DEFAULT_SCHEDULE, frequency: "hourly", minute: Number(minute) };
	}

	// Everything below requires concrete minute + hour.
	if (!isInt(minute) || !isInt(hour)) return null;

	const base = { hour: Number(hour), minute: Number(minute) };

	// Daily: "M H * * *"
	if (month === "*" && dom === "*" && dow === "*") {
		return { ...DEFAULT_SCHEDULE, ...base, frequency: "daily" };
	}

	// Weekdays: "M H * * 1-5"
	if (month === "*" && dom === "*" && dow === "1-5") {
		return { ...DEFAULT_SCHEDULE, ...base, frequency: "weekdays" };
	}

	// Weekly: "M H * * 1,3,5"
	if (month === "*" && dom === "*" && /^[0-6](,[0-6])*$/.test(dow)) {
		const daysOfWeek = [...new Set(dow.split(",").map(Number))].sort((a, b) => a - b);
		return { ...DEFAULT_SCHEDULE, ...base, frequency: "weekly", daysOfWeek };
	}

	// Monthly: "M H D * *"
	if (month === "*" && dow === "*" && isInt(dom)) {
		return { ...DEFAULT_SCHEDULE, ...base, frequency: "monthly", dayOfMonth: Number(dom) };
	}

	return null;
}
