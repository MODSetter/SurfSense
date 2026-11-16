import type { UsageReport } from "./usage-report-schema";

/**
 * desktop_usage_report's properties: the report flattened one level
 * (active_first, hardware_gpu, week_chat_turns, ...) plus the trigger and the country.
 * A section the report leaves null adds no properties.
 */
export function usageEventProperties(
	report: UsageReport,
	country: string
): Record<string, string | number | boolean> {
	const { active, hardware, week, trigger, ...top } = report;
	// Daily actives are counted from trigger "daily", which a 2.2.4 report implies.
	const properties: Record<string, string | number | boolean> = {
		...top,
		trigger: trigger ?? "daily",
	};
	for (const [section, values] of [
		["active", active],
		["hardware", hardware],
		["week", week],
	] as const) {
		for (const [key, value] of Object.entries(values ?? {})) {
			properties[`${section}_${key}`] = value;
		}
	}
	properties.country = country;
	return properties;
}
