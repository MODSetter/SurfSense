import { Fraunces } from "next/font/google";
import { getStarCount, STARS_HREF } from "@/components/site/github-stars";
import { SiteFooter } from "@/components/site/site-footer";
import { SiteNav } from "@/components/site/site-nav";
import { SiteSmoothScroll } from "@/components/site/site-smooth-scroll";
import "./home.css";

// Brand wordmark only; loaded here so only the marketing pages fetch it.
const fraunces = Fraunces({
	subsets: ["latin"],
	axes: ["SOFT", "WONK", "opsz"],
	display: "swap",
	variable: "--font-brand",
});

/**
 * Layout for every marketing route: the `.ss-home` palette, the nav, the ruled
 * column and the footer.
 *
 * Nothing here branches on the path: a `usePathname` check once served the
 * cached homepage without `.ss-home`, so it painted unstyled until hydration.
 *
 * The star count is cached in Next's Data Cache, fetched at most once an hour,
 * so these routes stay static.
 */
export default async function HomePageLayout({ children }: { children: React.ReactNode }) {
	const starCount = await getStarCount();

	return (
		<div className={`${fraunces.variable} contents`}>
			<main className="ss-home min-h-screen">
				{/* Outside the page slot, so React keeps the nav mounted across navigations. */}
				<SiteNav starCount={starCount} starsHref={STARS_HREF} />
				<SiteSmoothScroll />

				{/* Full width, so backgrounds can bleed; `.ss-home-page` (home.css) holds
				    each section to the column instead, and the footer caps its own content. */}
				<div className="ss-home-page">
					{children}
					<SiteFooter />
				</div>
			</main>
		</div>
	);
}
