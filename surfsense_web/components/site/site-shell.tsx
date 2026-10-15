"use client";

import { usePathname } from "next/navigation";
import { GlobalAnnouncement } from "@/components/homepage/global-announcement";
import { SiteFooter } from "@/components/site/site-footer";
import { SiteNav } from "@/components/site/site-nav";
import { SiteSmoothScroll } from "@/components/site/site-smooth-scroll";
import { getAllConnectorSlugs } from "@/lib/connectors-marketing";
import { cn } from "@/lib/utils";

/**
 * The chrome around every `(home)` route.
 *
 * This is the client half of the layout. It exists so that
 * `app/(home)/layout.tsx` can stay a server component and await the star count:
 * only the route branching below needs `usePathname`, and a `"use client"` on
 * the layout itself would have made the whole subtree unable to fetch anything.
 */

/**
 * Routes that have been moved onto the site design.
 *
 * They share the `.ss-home` palette from `home.css` and one ruled column, and
 * are styled with Tailwind plus the shared `siteText` styles. Every other route
 * under `(home)` still renders against `globals.css`; moving one over is a
 * matter of adding its path here and rebuilding its page on that design.
 *
 * The connector slugs (`/reddit`, `/amazon`, ...) are read from the registry
 * rather than listed by hand, so a page added to `lib/connectors-marketing`
 * lands on the site design automatically instead of falling back to the older
 * palette until someone remembers to list it here.
 */
const SITE_DESIGN_ROUTES = new Set([
	"/",
	"/pricing",
	"/private-ai-for-business",
	"/free",
	"/contact",
	"/plugins",
	"/blog",
	"/license",
	"/license/activate",
	"/license/success",
	"/downloads",
	"/changelog",
	"/announcements",
	"/login",
	"/sunset",
	"/external-mcp-connectors",
	"/mcp-server",
	"/privacy",
	"/terms",
	...getAllConnectorSlugs().map((slug) => `/${slug}`),
]);

/**
 * Prefixes for site-design routes with their own dynamic children, e.g. every
 * `/blog/<slug>` post under the `/blog` index.
 *
 * `/free/` covers every model page. Those used to bypass this shell entirely so
 * the anonymous chat could own the viewport; the hosted chat is closed and the
 * route is an ordinary marketing page now, so it takes the same chrome and
 * ruled column as the `/free` index above it.
 */
const SITE_DESIGN_PREFIXES = ["/blog/", "/free/"];

export function SiteShell({
	children,
	starCount,
	starsHref,
}: {
	children: React.ReactNode;
	starCount: number | null;
	starsHref: string;
}) {
	const pathname = usePathname();
	const isAuthPage = pathname === "/login" || pathname === "/register";

	const usesSiteDesign =
		SITE_DESIGN_ROUTES.has(pathname) ||
		SITE_DESIGN_PREFIXES.some((prefix) => pathname.startsWith(prefix));

	return (
		<main
			className={cn(
				"min-h-screen",
				// `ss-home` pins the canonical dark palette. It is a class swap rather
				// than a component swap on purpose: swapping the class repaints, while
				// swapping components would unmount the navigation below.
				usesSiteDesign
					? "ss-home"
					: "bg-linear-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white"
			)}
		>
			<GlobalAnnouncement />

			{/* Above every branch, so it is one element in one slot for every route.
			    React keeps it mounted across navigations and only the content below
			    changes. SiteNav also renders the announcement bar, just above its
			    sticky header. */}
			<SiteNav starCount={starCount} starsHref={starsHref} />
			{!isAuthPage ? <SiteSmoothScroll /> : null}

			{usesSiteDesign ? (
				// Full width, so backgrounds can bleed; `.ss-home-page` (home.css) holds
				// each section to the column instead, and the footer caps its own content.
				<div className="ss-home-page">
					{children}
					{!isAuthPage ? <SiteFooter /> : null}
				</div>
			) : (
				<>
					{/* `overflow-x: hidden` wraps the content rather than the whole page.
					    On the page element it would turn the layout into a scroll
					    container and the sticky navigation would stick inside *it*,
					    scrolling away with the content instead of staying at the top of
					    the viewport. */}
					<div className="overflow-x-hidden">{children}</div>

					{/* The footer caps its own content, so its image can run full width. */}
					{!isAuthPage ? <SiteFooter /> : null}
				</>
			)}
		</main>
	);
}
