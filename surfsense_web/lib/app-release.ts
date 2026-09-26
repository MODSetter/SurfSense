/**
 * The desktop release this site links to, and how its assets are named.
 *
 * `APP_RELEASE_VERSION` is written by `surfsense_local/scripts/bump-version.sh`.
 * It lives here because the web image builds with `context: ./surfsense_web`,
 * so nothing outside this directory exists at build time.
 *
 * No React and no directives, so server and client code can both import it.
 */

export const APP_RELEASE_VERSION = "2.0.3";

export const APP_RELEASE_TAG = `v${APP_RELEASE_VERSION}`;

/** The full list, for readers who want an older release or the changelog. */
export const GITHUB_RELEASES_URL = "https://github.com/MODSetter/SurfSense/releases";

export interface ReleaseAsset {
	name: string;
	url: string;
}

export const ASSET_LABELS: Record<string, string> = {
	".exe": "Windows (exe)",
	"-arm64.dmg": "macOS Apple Silicon (dmg)",
	"-x64.dmg": "macOS Intel (dmg)",
	"-arm64.zip": "macOS Apple Silicon (zip)",
	"-x64.zip": "macOS Intel (zip)",
	".AppImage": "Linux (AppImage)",
	".deb": "Linux (deb)",
};

export function getAssetLabel(name: string): string {
	for (const [suffix, label] of Object.entries(ASSET_LABELS)) {
		if (name.endsWith(suffix)) return label;
	}
	return name;
}
