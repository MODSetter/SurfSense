import { REPO_URL } from "@/components/site/site-content";
import type { PluginListing } from "./plugin-list";

/**
 * Third-party plugins, read from the signed list the app reads, so a newly listed
 * plugin reaches this page with no change here. Icons are the container's own copies.
 */

const REGISTRY_ORIGIN = "https://plugins.surfsense.com";
// The container caches the list for five minutes; the page need not be fresher than an hour.
const REFRESH_SECONDS = 3600;
const ICON_NAME = /^[a-z0-9][a-z0-9_-]*\.(svg|png)$/;
const REGISTRY_URL = `${REPO_URL}/tree/main/plugins/registry`;

type PublishedEntry = {
	id?: unknown;
	name?: unknown;
	description?: unknown;
	author?: unknown;
	homepage?: unknown;
	icon?: unknown;
	access?: unknown;
	verification?: unknown;
};

/** Empty when the container cannot be reached: the page renders without the row. */
export async function registryPlugins(): Promise<PluginListing[]> {
	try {
		const response = await fetch(`${REGISTRY_ORIGIN}/plugins.json`, {
			next: { revalidate: REFRESH_SECONDS },
		});
		if (!response.ok) return [];
		const list = (await response.json()) as { plugins?: PublishedEntry[] };
		return (list.plugins ?? []).flatMap((entry) => {
			const listing = asListing(entry);
			return listing ? [listing] : [];
		});
	} catch {
		return [];
	}
}

function asListing(entry: PublishedEntry): PluginListing | null {
	const { id, name, description, author } = entry;
	if (![id, name, description, author].every((field) => typeof field === "string")) return null;
	const homepage =
		typeof entry.homepage === "string" && entry.homepage.startsWith("https://")
			? entry.homepage
			: REGISTRY_URL;
	const icon = typeof entry.icon === "string" && ICON_NAME.test(entry.icon) ? entry.icon : null;
	return {
		id: id as string,
		name: name as string,
		description: description as string,
		author: author as string,
		href: homepage,
		logo: icon
			? { kind: "image", src: `${REGISTRY_ORIGIN}/icons/${icon}` }
			: { kind: "letter", letter: (name as string).trim().charAt(0) },
		publisher: "third-party",
		access: entry.access === "external" ? "external" : "free",
		verification: entry.verification === "verified" ? "verified" : "community",
	};
}
