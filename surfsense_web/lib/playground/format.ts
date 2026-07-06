/** Formatting helpers shared by the playground runs table and runner output. */

export function formatCost(costMicros: number | null | undefined): string {
	if (costMicros == null) return "—";
	if (costMicros === 0) return "Free";
	return `$${(costMicros / 1_000_000).toFixed(4)}`;
}

export function formatDuration(ms: number | null | undefined): string {
	if (ms == null) return "—";
	if (ms < 1000) return `${ms}ms`;
	return `${(ms / 1000).toFixed(1)}s`;
}
