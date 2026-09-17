/**
 * Sunset mode for the web app.
 *
 * At T-0 the hosted service becomes export-only, so the app itself has nothing
 * left to do: every signed-in route sends the user to `/sunset`, which carries
 * the export button, the download links and the import steps.
 *
 * Deliberately **not** `NEXT_PUBLIC_SUNSET_MODE`. `NEXT_PUBLIC_*` values are
 * inlined at build time, which would mean rebuilding and redeploying the image
 * to sunset -- while the backend reads its flag per request precisely so the
 * flip needs no deploy. This is read in middleware, which runs per request, so
 * both halves are thrown the same way: one variable, set in two places.
 */

import { isPublicRoute } from "@/lib/public-routes";

// The same spellings the backend accepts, for the same reason: the switch is
// thrown once, under time pressure, and a value that quietly reads as false
// would leave the app running as normal with nothing to show it had failed.
const TRUTHY = new Set(["1", "true", "yes", "on"]);

export function isSunsetMode(value: string | undefined | null): boolean {
	return TRUTHY.has(
		String(value ?? "")
			.trim()
			.toLowerCase()
	);
}

/**
 * Whether this request should be sent to `/sunset`.
 *
 * "Public" here means the wind-down portal itself -- `/sunset`, `/license`,
 * `/pricing`, the landing page, the blog. Those have to stay reachable, since
 * they are where a sunset user is being sent. Everything else is the app,
 * which has no hosted service left behind it.
 */
export function shouldRedirectToSunset(pathname: string, flag: string | undefined | null): boolean {
	if (!isSunsetMode(flag)) return false;
	return !isPublicRoute(pathname);
}
