import { getStarCount, STARS_HREF } from "@/components/site/github-stars";
import { SiteShell } from "@/components/site/site-shell";
import "./home.css";

/**
 * Layout for every marketing route.
 *
 * A server component so it can await the star count, which is cached in Next's
 * Data Cache and therefore fetched at most once an hour rather than once per
 * visitor. The route branching that needs `usePathname` lives in `SiteShell`,
 * the client half.
 *
 * The fetch is cached, so it does not opt these routes into dynamic rendering:
 * they stay static and are revalidated on the same hourly schedule.
 */
export default async function HomePageLayout({ children }: { children: React.ReactNode }) {
	const starCount = await getStarCount();

	return (
		<SiteShell starCount={starCount} starsHref={STARS_HREF}>
			{children}
		</SiteShell>
	);
}
