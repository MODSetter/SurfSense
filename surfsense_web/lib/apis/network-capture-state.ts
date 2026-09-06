/**
 * Page-lifecycle state deciding whether an API network failure is worth
 * reporting, and whether a reported one followed a reconnect.
 *
 * Separate from `base-api.service` for two reasons: it can be exercised
 * without pulling in the fetch stack, and the bfcache reset below fails
 * silently when broken — a tab that never clears the unloading flag stops
 * reporting network failures for the rest of its life.
 */

let unloading = false;
let lastOnlineAt: number | null = null;

/** True while the browser is discarding or freezing the page. */
export function isPageUnloading(): boolean {
	return unloading;
}

/**
 * Milliseconds since the browser last fired `online`, or null if it never did
 * during this page's life. A small value means the failure is almost certainly
 * a reconnect refetch racing an unusable connection, not a backend outage.
 */
export function msSinceOnline(now: number = Date.now()): number | null {
	return lastOnlineAt === null ? null : now - lastOnlineAt;
}

export function markUnloading(): void {
	unloading = true;
}

/** Called on `pageshow`, which is the only signal a bfcache page came back. */
export function markRestored(): void {
	unloading = false;
}

export function markOnline(at: number = Date.now()): void {
	lastOnlineAt = at;
}

if (typeof window !== "undefined") {
	// `pagehide` over `beforeunload`: it also covers bfcache entry and mobile
	// tab disposal, and does not block the navigation.
	window.addEventListener("pagehide", () => markUnloading());
	window.addEventListener("pageshow", () => markRestored());
	window.addEventListener("online", () => markOnline());
}
