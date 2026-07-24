/** Formatting helpers shared by the playground runs table and runner output. */

import type { ScraperPricingMeter } from "@/contracts/types/scraper.types";

export function formatCost(costMicros: number | null | undefined): string {
	if (costMicros == null) return "—";
	if (costMicros === 0) return "Free";
	return `$${(costMicros / 1_000_000).toFixed(4)}`;
}

/** One meter as a per-1k rate, e.g. 3500 micros/place -> "$3.50 / 1k places". */
export function formatRate(meter: ScraperPricingMeter): string {
	const perThousand = (meter.micros_per_unit * 1000) / 1_000_000;
	const dollars = Number.isInteger(perThousand) ? perThousand.toString() : perThousand.toFixed(2);
	return `$${dollars} / 1k ${meter.unit}s`;
}

/** A capability's full price line: "Free", one rate, or "rate + rate". */
export function formatPricing(pricing: ScraperPricingMeter[] | undefined): string {
	if (!pricing || pricing.length === 0) return "Free";
	return pricing.map(formatRate).join(" + ");
}

export function formatDuration(ms: number | null | undefined): string {
	if (ms == null) return "—";
	if (ms < 1000) return `${ms}ms`;
	return `${(ms / 1000).toFixed(1)}s`;
}
