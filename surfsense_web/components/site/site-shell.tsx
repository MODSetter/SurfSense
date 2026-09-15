"use client";

import { usePathname } from "next/navigation";
import { GlobalAnnouncement } from "@/components/homepage/global-announcement";
import { SiteFooter } from "@/components/site/site-footer";
import { SiteNav } from "@/components/site/site-nav";
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
 * Routes that have been moved onto the site design in `home.css`.
 *
 * They share one palette, one ruled column and one set of section primitives.
 * Every other route under `(home)` still renders against `globals.css`; moving
 * one over is a matter of adding its path here and rebuilding its page with the
 * `ss-home-*` classes.
 */
const SITE_DESIGN_ROUTES = new Set(["/", "/pricing", "/contact"]);

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
	const isFreeModelChat = /^\/free\/[^/]+$/.test(pathname);

	if (isFreeModelChat) {
		return <>{children}</>;
	}

	const usesSiteDesign = SITE_DESIGN_ROUTES.has(pathname);

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
			    changes. */}
			<SiteNav starCount={starCount} starsHref={starsHref} />

			{usesSiteDesign ? (
				// The footer is part of the page, not chrome around it: it sits inside
				// the same ruled column as every section above, so the side borders run
				// unbroken from the top of the page to the footer panel.
				<div className="ss-home-shell">
					{children}
					<SiteFooter />
				</div>
			) : (
				<>
					{/* `overflow-x: hidden` wraps the content rather than the whole page.
					    On the page element it would turn the layout into a scroll
					    container and the sticky navigation would stick inside *it*,
					    scrolling away with the content instead of staying at the top of
					    the viewport. */}
					<div className="overflow-x-hidden">{children}</div>

					{/* The same footer, held to the same column width. It is not wrapped
					    in `ss-home-shell` here: that draws the ruled side borders, which
					    would frame a footer sitting under content that has no such
					    frame. */}
					{!isAuthPage ? (
						<div className="mx-auto w-full max-w-[var(--home-max)]">
							<SiteFooter />
						</div>
					) : null}
				</>
			)}
		</main>
	);
}
