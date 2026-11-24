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
import { WebSearchLogo } from "@/components/site/logos/web-search-logo";
import { YoutubeLogo } from "@/components/site/logos/youtube-logo";
import { BUILT_IN_SOURCES, type BuiltInSource } from "./built-in-sources";
import firstPartyList from "./first-party-plugins.json";
import { listingFromEntry, type PluginListing } from "./plugin-listing";

/**
 * SurfSense's own plugins, from a copy of the app's list,
 * `surfsense_local/backend/modules/plugins/lists/first_party/plugins.json`; copy the
 * file over whenever it changes. Other publishers' are read from the registry, in
 * `registry-plugins.ts`.
 *
 * Reading pages, YouTube and web search are built into the app and listed from
 * `built-in-sources.ts` instead.
 */

export type { PluginListing } from "./plugin-listing";

type Logo = (props: React.SVGProps<SVGSVGElement>) => React.ReactElement;

// The site's own marks, sharper than the app's icon files at card size.
const LOGOS: Partial<Record<string, Logo>> = {
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

// Built-in search goes through SearXNG, not Google, so it does not wear Google's mark.
const BUILT_IN_LOGOS: Partial<Record<string, Logo>> = {
	"google-search": WebSearchLogo,
	"web-crawl": WebCrawlLogo,
	youtube: YoutubeLogo,
};

function listedPlugins(list: { plugins: unknown[] }): PluginListing[] {
	return list.plugins.flatMap((entry) => {
		const listing = listingFromEntry(entry, "surfsense");
		if (!listing) return [];
		const Logo = LOGOS[listing.id];
		return [Logo ? { ...listing, logo: { kind: "inline", Logo } } : listing];
	});
}

function builtInListing(source: BuiltInSource): PluginListing {
	const Logo = BUILT_IN_LOGOS[source.id];
	return {
		id: source.id,
		name: source.name,
		description: source.description,
		author: "SurfSense",
		href: `/plugins/${source.id}`,
		logo: Logo ? { kind: "inline", Logo } : { kind: "letter", letter: source.name.charAt(0) },
		publisher: "surfsense",
		access: "free",
		accessNote: null,
		signIn: "none",
		// No server of its own; its page names none.
		serverHost: "",
		signInHosts: [],
		tools: [],
		about: source.about,
		added: null,
		homepage: null,
		privacyPolicy: null,
		builtIn: true,
	};
}

/** An app list that still carries a built-in id lists it once, as built in. */
export function surfsensePlugins(appList: { plugins: unknown[] }) {
	const builtIn = BUILT_IN_SOURCES.map(builtInListing);
	const builtInIds = new Set(builtIn.map((plugin) => plugin.id));
	return [...builtIn, ...listedPlugins(appList).filter((plugin) => !builtInIds.has(plugin.id))];
}

export const SURFSENSE_PLUGINS: PluginListing[] = surfsensePlugins(firstPartyList);

/** Hand picked, ours and other publishers'; an id the registry no longer lists is skipped. */
export const FEATURED_IDS = ["google-search", "youtube", "deepwiki", "notion"];
