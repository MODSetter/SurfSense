import { googleMaps } from "./google-maps";
import { googleSearch } from "./google-search";
import { reddit } from "./reddit";
import { tiktok } from "./tiktok";
import type { ConnectorPageContent } from "./types";
import { webCrawl } from "./web-crawl";
import { youtube } from "./youtube";

export type { ConnectorPageContent } from "./types";

/** Registry order controls sitemap and cross-link ordering. */
const CONNECTOR_LIST: ConnectorPageContent[] = [
	reddit,
	youtube,
	tiktok,
	googleMaps,
	googleSearch,
	webCrawl,
];

const CONNECTORS_BY_SLUG: Record<string, ConnectorPageContent> = Object.fromEntries(
	CONNECTOR_LIST.map((c) => [c.slug, c])
);

export function getConnector(slug: string): ConnectorPageContent | undefined {
	return CONNECTORS_BY_SLUG[slug];
}

export function getAllConnectors(): ConnectorPageContent[] {
	return CONNECTOR_LIST;
}

export function getAllConnectorSlugs(): string[] {
	return CONNECTOR_LIST.map((c) => c.slug);
}
