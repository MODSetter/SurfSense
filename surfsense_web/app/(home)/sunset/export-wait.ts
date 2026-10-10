/**
 * What the export step says while the account ZIP is being built.
 *
 * The server builds the whole archive before it sends the first byte, so a
 * large account is a long wait with nothing to show for it. Nothing is said
 * for the first few seconds, which is as long as most accounts take: measured
 * for #2006, an account of 20,000 documents builds in about 5 s and one of
 * 100,000 in about 25 s. Past that the reader is told it is still working,
 * for how long, and to keep the tab open.
 */

export const SLOW_EXPORT_AFTER_SECONDS = 10;

function formatElapsed(seconds: number): string {
	const whole = Math.floor(seconds);
	if (whole < 60) return `${whole} s`;
	const minutes = Math.floor(whole / 60);
	const rest = whole % 60;
	return rest === 0 ? `${minutes} min` : `${minutes} min ${rest} s`;
}

export function exportWaitMessage(elapsedSeconds: number): string | null {
	if (elapsedSeconds < SLOW_EXPORT_AFTER_SECONDS) return null;
	return `Still building your export (${formatElapsed(elapsedSeconds)} so far). A large account can take a few minutes. Keep this tab open.`;
}
