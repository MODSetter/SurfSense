import "server-only";

import { APP_RELEASE_TAG, type ReleaseAsset } from "@/lib/app-release";

const INSTALLER = /\.(exe|dmg|AppImage|deb)$/;

export function releaseApiUrl(tag: string): string {
	return `https://api.github.com/repos/MODSetter/SurfSense/releases/tags/${tag}`;
}

export function parseAssets(data: unknown): ReleaseAsset[] {
	const assets = (data as { assets?: unknown })?.assets;
	if (!Array.isArray(assets)) return [];
	return assets
		.filter((a): a is { name: string; browser_download_url: string } => INSTALLER.test(a?.name))
		.map((a) => ({ name: a.name, url: a.browser_download_url }));
}

/**
 * Installers for the release named in `app-release.ts`.
 *
 * Server-side and cached, because the browser version of this call is
 * unauthenticated and capped at 60/hour per IP: one office behind a shared
 * address empties the grid for everyone on it. Rendering here also puts the
 * links in the HTML, which the client fetch never did.
 *
 * Returns `[]` rather than throwing. The page shows the releases link
 * instead, which is a worse answer than a download but a better one than
 * placeholders that never resolve.
 */
export async function getReleaseAssets(): Promise<ReleaseAsset[]> {
	try {
		const response = await fetch(releaseApiUrl(APP_RELEASE_TAG), {
			headers: { Accept: "application/vnd.github+json" },
			next: { revalidate: 3600 },
		});
		if (!response.ok) return [];
		return parseAssets(await response.json());
	} catch {
		return [];
	}
}
