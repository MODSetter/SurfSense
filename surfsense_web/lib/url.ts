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
