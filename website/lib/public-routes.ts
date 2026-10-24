/**
 * Which routes are reachable without a session.
 *
 * Kept apart from `auth-utils` so a predicate never drags in helpers that touch
 * `window` and `localStorage`.
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
	// The cross-cutting professional page. A marketing route missing from this
	// list still renders, but only on the client: `ZeroProvider` mounts the
	// authenticated sync provider for it, which emits no SSR HTML, so a crawler
	// sees an empty shell.
	"/private-ai-for-business",
	"/privacy",
	"/terms",
	"/changelog",
	"/announcements",
	"/blog",
	// The plugins gallery and each plugin's page, `/plugins/<id>`.
	"/plugins",
	"/connectors",
	"/mcp-server",
	"/external-mcp-connectors",
];

/**
 * Returns true if the pathname is a public route where we should not run auth checks
 * or redirect to login on 401.
 */
export function isPublicRoute(pathname: string): boolean {
	if (pathname === "/" || pathname === "") return true;
	return PUBLIC_ROUTE_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}
