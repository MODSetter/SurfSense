import type * as React from "react";
import { AmazonLogo } from "@/components/homepage/icons/amazon-logo";
import { GoogleMapsLogo } from "@/components/homepage/icons/google-maps-logo";
import { GoogleSearchLogo } from "@/components/homepage/icons/google-search-logo";
import { IndeedLogo } from "@/components/homepage/icons/indeed-logo";
import { TiktokLogo } from "@/components/homepage/icons/tiktok-logo";
import { WalmartLogo } from "@/components/homepage/icons/walmart-logo";
import { WebCrawlLogo } from "@/components/homepage/icons/web-crawl-logo";
import { YoutubeLogo } from "@/components/homepage/icons/youtube-logo";

/**
 * SurfSense's own plugins, and the shape every listing on the page takes.
 *
 * SurfSense's own mirror `surfsense_local/backend/modules/plugins/lists/first_party/plugins.json`;
 * change them together. Other publishers' are read from the registry, in `registry-plugins.ts`.
 * Reddit and Instagram are written but left out of the app's list, because
 * both close their public pages to readers who are not signed in.
 */

export type PluginListing = {
	id: string;
	name: string;
	description: string;
	author: string;
	/** A marketing page under `lib/connectors-marketing`, or the publisher's homepage. */
	href: string;
	logo:
		| { kind: "inline"; Logo: (props: React.SVGProps<SVGSVGElement>) => React.ReactElement }
		| { kind: "image"; src: string }
		| { kind: "letter"; letter: string };
	publisher: "surfsense" | "third-party";
	access: "license" | "free" | "external";
	verification?: "verified" | "community";
};

export const SURFSENSE_PLUGINS: PluginListing[] = [
	{
		id: "google-search",
		name: "Google Search",
		description: "Search Google and read its results, ads and related questions.",
		author: "SurfSense",
		href: "/google-search",
		logo: { kind: "inline", Logo: GoogleSearchLogo },
		publisher: "surfsense",
		access: "license",
	},
	{
		id: "web-crawl",
		name: "Web Crawl",
		description: "Read a web page, or crawl a whole site into clean text.",
		author: "SurfSense",
		href: "/web-crawl",
		logo: { kind: "inline", Logo: WebCrawlLogo },
		publisher: "surfsense",
		access: "license",
	},
	{
		id: "youtube",
		name: "YouTube",
		description: "Read YouTube videos, channels and their comments.",
		author: "SurfSense",
		href: "/youtube",
		logo: { kind: "inline", Logo: YoutubeLogo },
		publisher: "surfsense",
		access: "license",
	},
	{
		id: "tiktok",
		name: "TikTok",
		description: "Read TikTok videos and their comments, search users, and see what is trending.",
		author: "SurfSense",
		href: "/tiktok",
		logo: { kind: "inline", Logo: TiktokLogo },
		publisher: "surfsense",
		access: "license",
	},
	{
		id: "google-maps",
		name: "Google Maps",
		description: "Find places on Google Maps and read their reviews.",
		author: "SurfSense",
		href: "/google-maps",
		logo: { kind: "inline", Logo: GoogleMapsLogo },
		publisher: "surfsense",
		access: "license",
	},
	{
		id: "amazon",
		name: "Amazon",
		description: "Read Amazon products and search results.",
		author: "SurfSense",
		href: "/amazon",
		logo: { kind: "inline", Logo: AmazonLogo },
		publisher: "surfsense",
		access: "license",
	},
	{
		id: "walmart",
		name: "Walmart",
		description: "Read Walmart products, search results and reviews.",
		author: "SurfSense",
		href: "/walmart",
		logo: { kind: "inline", Logo: WalmartLogo },
		publisher: "surfsense",
		access: "license",
	},
	{
		id: "indeed",
		name: "Indeed",
		description: "Read job listings on Indeed.",
		author: "SurfSense",
		href: "/indeed",
		logo: { kind: "inline", Logo: IndeedLogo },
		publisher: "surfsense",
		access: "license",
	},
];

/** Hand picked, ours and other publishers'; an id the registry no longer lists is skipped. */
export const FEATURED_IDS = ["google-search", "youtube", "deepwiki", "notion"];
