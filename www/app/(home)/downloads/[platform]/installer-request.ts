import {
	APP_RELEASE_VERSION,
	FIRST_STABLE_NAMES_VERSION,
	type InstallerPlatform,
	isInstallerPlatform,
} from "@/features/downloads/app-release";

/** Where the link that led here lives. Anything else is counted as `other`. */
export const DOWNLOAD_SOURCES = ["site", "readme", "email", "app", "pricing", "other"] as const;

export type DownloadSource = (typeof DOWNLOAD_SOURCES)[number];

/** What the link asks for. Whether GitHub serves that build yet is `installer-location.ts`. */
export type InstallerRequest = {
	platform: InstallerPlatform;
	src: DownloadSource;
	version: string;
};

const VERSION = /^v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})$/;

function parseVersion(value: string): [number, number, number] | null {
	const match = VERSION.exec(value);
	if (!match) return null;
	return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function isAtLeast(a: [number, number, number], b: [number, number, number]): boolean {
	for (let index = 0; index < 3; index++) {
		if (a[index] !== b[index]) return a[index] > b[index];
	}
	return true;
}

/**
 * A pinned link (`v`, which the licence email sends) keeps its build. Anything
 * older than the stable file names, or not a plain release tag, gets the
 * release this deployment pins instead.
 */
function resolveVersion(requested: string | null): string {
	const floor = parseVersion(FIRST_STABLE_NAMES_VERSION);
	const parsed = requested ? parseVersion(requested.trim()) : null;
	if (parsed && floor && isAtLeast(parsed, floor)) return parsed.join(".");
	return APP_RELEASE_VERSION;
}

function resolveSource(requested: string | null): DownloadSource {
	const source = (requested ?? "").trim().toLowerCase();
	return (DOWNLOAD_SOURCES as readonly string[]).includes(source)
		? (source as DownloadSource)
		: "other";
}

/** The installer a `/downloads/<platform>` link asks for, or null for an unknown platform. */
export function readInstallerRequest(
	platform: string,
	params: URLSearchParams
): InstallerRequest | null {
	if (!isInstallerPlatform(platform)) return null;
	return {
		platform,
		src: resolveSource(params.get("src")),
		version: resolveVersion(params.get("v")),
	};
}

/** Vercel's two-letter country for the request, or null when absent or malformed. */
export function countryFromHeader(value: string | null): string | null {
	const country = (value ?? "").trim().toUpperCase();
	return /^[A-Z]{2}$/.test(country) ? country : null;
}
