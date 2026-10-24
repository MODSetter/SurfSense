/** Release tag → the asset names GitHub serves for it to anyone signed out. */
export type PublishedInstallers = ReadonlyMap<string, ReadonlySet<string>>;

/**
 * The newest 30 releases, about 0.9 MB, under the 2 MB a cached fetch may hold.
 * A tag older than that falls back to Latest, which is still a working installer.
 */
const RELEASES_API = "https://api.github.com/repos/MODSetter/SurfSense/releases?per_page=30";

/** Drafts are skipped: their assets 404 for anyone but the repository's maintainers. */
export function parsePublishedInstallers(data: unknown): PublishedInstallers {
	const published = new Map<string, ReadonlySet<string>>();
	if (!Array.isArray(data)) return published;
	for (const release of data) {
		if (!release || typeof release !== "object" || release.draft !== false) continue;
		if (typeof release.tag_name !== "string" || !Array.isArray(release.assets)) continue;
		const names = release.assets
			.map((asset: unknown) => (asset as { name?: unknown })?.name)
			.filter((name: unknown): name is string => typeof name === "string");
		published.set(release.tag_name, new Set(names));
	}
	return published;
}

/**
 * Cached for an hour, like the /downloads grid's lookup, because the GitHub API
 * allows 60 unauthenticated calls an hour. Null when GitHub could not be asked.
 */
export async function getPublishedInstallers(): Promise<PublishedInstallers | null> {
	try {
		const response = await fetch(RELEASES_API, {
			headers: { Accept: "application/vnd.github+json" },
			next: { revalidate: 3600 },
		});
		if (!response.ok) return null;
		return parsePublishedInstallers(await response.json());
	} catch {
		return null;
	}
}
