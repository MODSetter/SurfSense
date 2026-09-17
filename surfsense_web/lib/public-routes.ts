/**
 * Which routes are reachable without a session.
 *
 * Kept apart from `auth-utils` so the edge middleware can import the predicate
 * without dragging in helpers that touch `window` and `localStorage`. Two
 * consumers rely on it: the auth redirect, and the sunset redirect, which
 * treats "public" as "part of the wind-down portal, leave it reachable".
 */

/** Path prefixes for routes that do not require auth (no current-user fetch, no redirect on 401) */
const PUBLIC_ROUTE_PREFIXES = [
	"/login",
	"/register",
	"/auth",
	"/desktop/login",
	"/docs",
	"/public",
	"/free",
	"/invite",
	"/contact",
	"/downloads",
	// The license portal and the post-purchase success page. There is no
	// account to sign in to, and the buyer lands on /license/success straight
	// from Stripe -- a login redirect there loses them their license file.
	"/license",
	"/pricing",
	"/privacy",
	"/terms",
	"/changelog",
	"/announcements",
	"/blog",
	"/sunset",
	// Plugins coming-soon page.
	"/plugins",
	// Connector marketing pages (see lib/connectors-marketing)
	"/connectors",
	"/mcp-server",
	"/external-mcp-connectors",
	"/reddit",
	"/instagram",
	"/tiktok",
	"/youtube",
	"/google-maps",
	"/google-search",
	"/indeed",
	"/web-crawl",
	"/amazon",
	"/walmart",
];

/**
 * Returns true if the pathname is a public route where we should not run auth checks
 * or redirect to login on 401.
 */
export function isPublicRoute(pathname: string): boolean {
	if (pathname === "/" || pathname === "") return true;
	return PUBLIC_ROUTE_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}
