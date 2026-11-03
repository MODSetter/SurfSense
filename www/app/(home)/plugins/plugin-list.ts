import type * as React from "react";
import { AmazonLogo } from "@/components/site/logos/amazon-logo";
import { GoogleMapsLogo } from "@/components/site/logos/google-maps-logo";
import { GoogleSearchLogo } from "@/components/site/logos/google-search-logo";
import { IndeedLogo } from "@/components/site/logos/indeed-logo";
import { InstagramLogo } from "@/components/site/logos/instagram-logo";
import { RedditLogo } from "@/components/site/logos/reddit-logo";
import { TiktokLogo } from "@/components/site/logos/tiktok-logo";
import { WalmartLogo } from "@/components/site/logos/walmart-logo";
import { WebCrawlLogo } from "@/components/site/logos/web-crawl-logo";
import { YoutubeLogo } from "@/components/site/logos/youtube-logo";
import { BUSINESS_LAUNCHED } from "@/features/business-launch/business-launched.mts";
import firstPartyList from "./first-party-plugins.json";
import listBeforeBusiness from "./first-party-plugins-before-business.json";
import { listingFromEntry, type PluginListing } from "./plugin-listing";

/**
 * SurfSense's own plugins, from a copy of the app's list,
 * `surfsense_local/backend/modules/plugins/lists/first_party/plugins.json`; copy the
 * file over whenever it changes. Other publishers' are read from the registry, in
 * `registry-plugins.ts`.
 *
 * Until Business goes on sale the site shows the list as it stood before the scrapers
 * retired, frozen in `first-party-plugins-before-business.json`, whatever the copy holds.
 */

export type { PluginListing } from "./plugin-listing";

// The site's own marks, sharper than the app's icon files at card size.
const LOGOS: Partial<Record<string, (props: React.SVGProps<SVGSVGElement>) => React.ReactElement>> =
	{
		"google-search": GoogleSearchLogo,
		"web-crawl": WebCrawlLogo,
		reddit: RedditLogo,
		youtube: YoutubeLogo,
		instagram: InstagramLogo,
		tiktok: TiktokLogo,
		"google-maps": GoogleMapsLogo,
		amazon: AmazonLogo,
		walmart: WalmartLogo,
		indeed: IndeedLogo,
	};

const SHOWN_LIST: { plugins: unknown[] } = BUSINESS_LAUNCHED ? firstPartyList : listBeforeBusiness;

export const SURFSENSE_PLUGINS: PluginListing[] = SHOWN_LIST.plugins.flatMap((entry) => {
	const listing = listingFromEntry(entry, "surfsense");
	if (!listing) return [];
	const Logo = LOGOS[listing.id];
	return [Logo ? { ...listing, logo: { kind: "inline", Logo } } : listing];
});

/** Hand picked, ours and other publishers'; an id the registry no longer lists is skipped. */
export const FEATURED_IDS = ["google-search", "youtube", "deepwiki", "notion"];
