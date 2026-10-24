export type BannerPlacement = "hidden" | "fixed" | "dismissible";

// Shared-chat visitors are not users of this install, and /desktop/* is the
// retired desktop app's sign-in handoff.
const HIDDEN_PREFIXES = ["/public/", "/desktop/"];

// The first page a visitor sees; the notice costs them nothing there.
const FIXED_PREFIXES = ["/login", "/register"];

/** Whether the desktop-app banner shows on a route, and whether it can be dismissed there. */
export function bannerPlacement(pathname: string): BannerPlacement {
	if (HIDDEN_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return "hidden";
	if (FIXED_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return "fixed";
	return "dismissible";
}
