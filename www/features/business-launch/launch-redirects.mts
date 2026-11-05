/**
 * Redirects that change with the Business launch switch, for `next.config.mts`. Kept out of
 * it, like `docs-redirects.mts`, so `launch-redirects.test.ts` can check them.
 *
 * Permanent: once Business is on sale, the Individual licence and the retired scrapers do not
 * come back, and browsers cache the redirect, so turning the switch off again would not undo it.
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

/** The platform scrapers that retire when Business goes on sale. */
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
function pluginRedirects(launched: boolean): Redirect[] {
	const scraperPages = SCRAPER_PAGES.map((id) => ({
		source: `/${id}`,
		destination: launched && RETIRED_PLUGIN_IDS.includes(id) ? "/plugins" : `/plugins/${id}`,
		permanent: true,
	}));
	if (!launched) return scraperPages;
	return [
		...scraperPages,
		...RETIRED_PLUGIN_IDS.map((id) => ({
			source: `/plugins/${id}`,
			destination: "/plugins",
			permanent: true,
		})),
	];
}

/** Individual is no longer sold, so its checkout page hands over to Business's. */
function pricingRedirects(launched: boolean): Redirect[] {
	return launched
		? [{ source: "/pricing/individual", destination: "/pricing/business", permanent: true }]
		: [];
}

export function launchRedirects(launched: boolean): Redirect[] {
	return [...pluginRedirects(launched), ...pricingRedirects(launched)];
}
