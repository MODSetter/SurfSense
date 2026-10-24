import type { UsageReport } from "./usage-report-schema";

/**
 * desktop_usage_report's properties: the report flattened one level
 * (active_first, hardware_gpu, week_chat_turns, ...) plus the country.
 * A section the report leaves null adds no properties.
 */
export function usageEventProperties(
	report: UsageReport,
	country: string
): Record<string, string | number | boolean> {
	const { active, hardware, week, ...top } = report;
	const properties: Record<string, string | number | boolean> = { ...top };
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
