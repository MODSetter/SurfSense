import { listingFromEntry, type PluginListing, REGISTRY_ORIGIN } from "./plugin-listing";

/**
 * Third-party plugins, read from the signed list the app reads, so a newly listed
 * plugin reaches this page, and gets a page of its own, with no change here.
 * Icons are the container's own copies.
 */

// The container caches the list for five minutes; the page need not be fresher than an hour.
export const REFRESH_SECONDS = 3600;

/** Empty when the container cannot be reached: the page renders without the row. */
export async function registryPlugins(): Promise<PluginListing[]> {
	try {
		const response = await fetch(`${REGISTRY_ORIGIN}/plugins.json`, {
			next: { revalidate: REFRESH_SECONDS },
		});
		if (!response.ok) return [];
		const list = (await response.json()) as { plugins?: unknown[] };
		return (list.plugins ?? []).flatMap((entry) => {
			const listing = listingFromEntry(entry, "third-party");
			return listing ? [listing] : [];
		});
	} catch {
		return [];
	}
}
