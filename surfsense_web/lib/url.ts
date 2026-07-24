/**
 * Extract a normalized hostname from a URL. Strips a leading `www.`.
 * Returns `undefined` if the input is not a parseable URL.
 *
 * This is the canonical replacement for the four previously-duplicated
 * `extractDomain` helpers that had subtly different error fallbacks.
 */
export function tryGetHostname(url: string): string | undefined {
	try {
		return new URL(url).hostname.replace(/^www\./, "");
	} catch {
		return undefined;
	}
}

/** True when the value parses as an http(s) URL — mirrors the backend's boundary rule. */
export function isHttpUrl(value: string): boolean {
	try {
		const { protocol } = new URL(value);
		return protocol === "http:" || protocol === "https:";
	} catch {
		return false;
	}
}
