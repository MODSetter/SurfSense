/**
 * Redirects for what retired when Business went on sale, the platform scrapers and the
 * Individual licence, for `next.config.mts`. Kept out of it, like `docs-redirects.mts`, so
 * `launch-redirects.test.ts` can check them.
 *
 * Permanent: the Individual licence and the retired scrapers do not come back.
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

/** Individual is no longer sold, so its checkout page hands over to Business's. */
const PRICING_REDIRECTS: Redirect[] = [
	{ source: "/pricing/individual", destination: "/pricing/business", permanent: true },
];

export function launchRedirects(): Redirect[] {
	return [...pluginRedirects(), ...PRICING_REDIRECTS];
}
