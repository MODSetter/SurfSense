/**
 * The desktop release this site links to, and how its assets are named.
 *
 * `APP_RELEASE_VERSION` is written by `surfsense_local/scripts/bump-version.sh`.
 * It lives here because Vercel builds from `www/` as the root directory,
 * so nothing outside it is a dependency the build can rely on.
 *
 * No React and no directives, so server and client code can both import it.
 */

export const APP_RELEASE_VERSION = "2.2.3";

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
	".rpm": "Linux (rpm)",
};

/**
 * What the site lists from a release: the installers a person downloads. The
 * macOS update zip, the manifests, SHA256SUMS, the install scripts and the apt
 * index are read by tools, and the snap installs from the Snap Store.
 */
const OFFERED_INSTALLER = /\.(exe|dmg|AppImage|deb|rpm)$/;

export function isOfferedInstaller(name: string): boolean {
	return OFFERED_INSTALLER.test(name);
}

export function getAssetLabel(name: string): string {
	for (const [suffix, label] of Object.entries(ASSET_LABELS)) {
		if (name.endsWith(suffix)) return label;
	}
	return name;
}

/**
 * The installer behind each `/downloads/<platform>` redirect. Every release from
 * 2.0.2 on publishes these names, the rpm only from the release that added its
 * target; a release without the file sends that platform to Latest. 2.0.0 and
 * 2.0.1 put the version in them. Renaming one breaks the redirect for every tag
 * already linked.
 */
export const INSTALLER_FILES = {
	windows: "SurfSense-Setup.exe",
	mac: "SurfSense-arm64.dmg",
	"linux-appimage": "SurfSense.AppImage",
	"linux-deb": "SurfSense.deb",
	"linux-rpm": "SurfSense.rpm",
} as const;

export type InstallerPlatform = keyof typeof INSTALLER_FILES;

/** The oldest release whose installers carry the names above. */
export const FIRST_STABLE_NAMES_VERSION = "2.0.2";

export function isInstallerPlatform(value: string): value is InstallerPlatform {
	return Object.hasOwn(INSTALLER_FILES, value);
}

export function installerAssetUrl(version: string, platform: InstallerPlatform): string {
	return `${GITHUB_RELEASES_URL}/download/v${version}/${INSTALLER_FILES[platform]}`;
}

/** The installer on whichever published release GitHub marks Latest. */
export function latestInstallerUrl(platform: InstallerPlatform): string {
	return `${GITHUB_RELEASES_URL}/latest/download/${INSTALLER_FILES[platform]}`;
}

export function platformOfAsset(name: string): InstallerPlatform | null {
	for (const [platform, file] of Object.entries(INSTALLER_FILES)) {
		if (name === file) return platform as InstallerPlatform;
	}
	return null;
}
