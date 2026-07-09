import type { ComponentType } from "react";
import {
	GoogleMapsIcon,
	GoogleSearchIcon,
	InstagramIcon,
	RedditIcon,
	WebIcon,
	YouTubeIcon,
} from "./platform-icons";

/** Icon component that accepts a ``className`` (Tabler + Lucide both satisfy this). */
export type PlatformIcon = ComponentType<{ className?: string }>;

/**
 * Static catalog of the platform-native scraper verbs, used to render the
 * playground navigation (sidebar + index grid) without waiting on a fetch.
 * Verb ``name`` mirrors the backend capability registry ``platform.verb`` and
 * maps directly to the REST path ``/scrapers/{platform}/{verb}``.
 */
export interface PlaygroundVerb {
	/** Capability name, e.g. ``reddit.scrape``. */
	name: string;
	/** URL segment, e.g. ``scrape``. */
	verb: string;
	label: string;
}

export interface PlaygroundPlatform {
	/** URL segment + REST platform, e.g. ``google_maps``. */
	id: string;
	label: string;
	icon: PlatformIcon;
	verbs: PlaygroundVerb[];
}

export const PLAYGROUND_PLATFORMS: PlaygroundPlatform[] = [
	{
		id: "reddit",
		label: "Reddit",
		icon: RedditIcon,
		verbs: [{ name: "reddit.scrape", verb: "scrape", label: "Scrape" }],
	},
	{
		id: "youtube",
		label: "YouTube",
		icon: YouTubeIcon,
		verbs: [
			{ name: "youtube.scrape", verb: "scrape", label: "Scrape" },
			{ name: "youtube.comments", verb: "comments", label: "Comments" },
		],
	},
	{
		id: "instagram",
		label: "Instagram",
		icon: InstagramIcon,
		verbs: [
			{ name: "instagram.scrape", verb: "scrape", label: "Scrape" },
			{ name: "instagram.comments", verb: "comments", label: "Comments" },
			{ name: "instagram.details", verb: "details", label: "Details" },
		],
	},
	{
		id: "google_maps",
		label: "Google Maps",
		icon: GoogleMapsIcon,
		verbs: [
			{ name: "google_maps.scrape", verb: "scrape", label: "Scrape" },
			{ name: "google_maps.reviews", verb: "reviews", label: "Reviews" },
		],
	},
	{
		id: "google_search",
		label: "Google Search",
		icon: GoogleSearchIcon,
		verbs: [{ name: "google_search.scrape", verb: "scrape", label: "Scrape" }],
	},
	{
		id: "web",
		label: "Web",
		icon: WebIcon,
		verbs: [{ name: "web.crawl", verb: "crawl", label: "Crawl" }],
	},
];

export function findPlatform(platformId: string): PlaygroundPlatform | undefined {
	return PLAYGROUND_PLATFORMS.find((p) => p.id === platformId);
}

export function findVerb(platformId: string, verb: string): PlaygroundVerb | undefined {
	return findPlatform(platformId)?.verbs.find((v) => v.verb === verb);
}
