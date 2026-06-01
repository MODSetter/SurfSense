/**
 * Format the wall-clock duration between a run/step's start and finish
 * timestamps into a compact, human-readable label (e.g. `850ms`, `4.2s`,
 * `1m 30s`). Returns `null` when either bound is missing or the delta is
 * negative/non-finite, so callers can simply omit the label.
 */
export function formatDuration(
	started: string | null | undefined,
	finished: string | null | undefined
): string | null {
	if (!started || !finished) return null;
	const ms = new Date(finished).getTime() - new Date(started).getTime();
	if (!Number.isFinite(ms) || ms < 0) return null;
	if (ms < 1000) return `${ms}ms`;
	if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
	const minutes = Math.floor(ms / 60_000);
	const seconds = Math.floor((ms % 60_000) / 1000);
	return `${minutes}m ${seconds}s`;
}
