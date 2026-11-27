/**
 * Redirects for what retired, the platform scrapers, the paid plans and the hosted MCP
 * server's page, for `next.config.mts`. Kept out of it, like `docs-redirects.mts`, so
 * `launch-redirects.test.ts` can check them.
 *
 * The retired scrapers' redirects are permanent: they do not come back. The old pricing
 * pages' and the MCP server page's are temporary, because a browser caches a 308 for good
 * and either may come back; never add a permanent redirect to a page that may go away.
 */

type Redirect = { source: string; destination: string; permanent: boolean };

/** The per-scraper marketing pages, which gave way to each plugin's page under /plugins. */
const SCRAPER_PAGES = [
	"google-search",
	"web-crawl",
	"reddit",
	"youtube",
	"instagram",
	"tiktok",
	"google-maps",
	"amazon",
	"walmart",
	"indeed",
];

/** The platform scrapers that retired when Business went on sale. */
export const RETIRED_PLUGIN_IDS = [
	"reddit",
	"instagram",
	"tiktok",
	"google-maps",
	"amazon",
	"walmart",
	"indeed",
];

/**
 * A retired scraper's page and its old address go to `/plugins`, which lists what replaced
 * them, rather than through a page that no longer exists.
 */
function pluginRedirects(): Redirect[] {
	return [
		...SCRAPER_PAGES.map((id) => ({
			source: `/${id}`,
			destination: RETIRED_PLUGIN_IDS.includes(id) ? "/plugins" : `/plugins/${id}`,
			permanent: true,
		})),
		...RETIRED_PLUGIN_IDS.map((id) => ({
			source: `/plugins/${id}`,
			destination: "/plugins",
			permanent: true,
		})),
	];
}

/** SurfSense is free, so the old checkout pages hand over to `/pricing`, which says so. */
const PRICING_REDIRECTS: Redirect[] = [
	{ source: "/pricing/individual", destination: "/pricing", permanent: false },
	{ source: "/pricing/business", destination: "/pricing", permanent: false },
];

/**
 * `/mcp-server` advertised SurfSense's hosted MCP server, which closes with SurfSense Inc. on
 * 27 November 2026. The page is retired for now, so its visitors go to the home page.
 */
const RETIRED_PAGE_REDIRECTS: Redirect[] = [
	{ source: "/mcp-server", destination: "/", permanent: false },
];

export function launchRedirects(): Redirect[] {
	return [...pluginRedirects(), ...PRICING_REDIRECTS, ...RETIRED_PAGE_REDIRECTS];
}
