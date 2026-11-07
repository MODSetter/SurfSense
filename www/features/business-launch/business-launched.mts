/**
 * The Business launch switch, `NEXT_PUBLIC_BUSINESS_LAUNCHED`. Off, the site is the one from
 * before Business went on sale; on, it sells Business and lists the scrapers as retired.
 * Flip it on the day the release that ships the paid jobs goes out. NEXT_PUBLIC_* is
 * baked in at `next build`, so a change needs a redeploy.
 *
 * A `.mts`, like `docs-redirects.mts`, so `next.config.mts` can read it too.
 */

/** Only the exact string "true" turns it on, as with the announcement switches. */
export function isBusinessLaunched(value: string | undefined): boolean {
	return value === "true";
}

export const BUSINESS_LAUNCHED = isBusinessLaunched(process.env.NEXT_PUBLIC_BUSINESS_LAUNCHED);
