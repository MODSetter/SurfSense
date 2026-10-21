/**
 * App version, platform and OS as the desktop app reports them
 * (docs/contracts/05-desktop-telemetry.md). Both routes accept only these
 * spellings, so nothing free-form reaches an event.
 */

export const DESKTOP_PLATFORMS = [
	"win32-x64",
	"win32-arm64",
	"darwin-arm64",
	"darwin-x64",
	"linux-x64",
	"linux-arm64",
] as const;

const FIXED_OS_NAMES = new Set(["windows-10", "windows-11", "linux"]);
const MACOS_MAJOR = /^macos-[1-9][0-9]$/;

// Plain x.y.z only: a pre-release tag is free text and could carry a name, so
// a pre-release build's checks count as "invalid" and its usage reports get 400.
export const APP_VERSION = /^(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})$/;

export function isDesktopPlatform(value: unknown): value is (typeof DESKTOP_PLATFORMS)[number] {
	return typeof value === "string" && (DESKTOP_PLATFORMS as readonly string[]).includes(value);
}

export function isDesktopOs(value: unknown): value is string {
	return typeof value === "string" && (FIXED_OS_NAMES.has(value) || MACOS_MAJOR.test(value));
}

export function isAppVersion(value: unknown): value is string {
	return typeof value === "string" && APP_VERSION.test(value);
}

export type UpdateCheckDimensions = {
	app_version: string;
	platform: string;
	os: string;
};

/** Reads the three X-SurfSense-* headers, folding anything unexpected into one bucket. */
export function readUpdateCheckDimensions(headers: Headers): UpdateCheckDimensions {
	const version = headers.get("x-surfsense-version");
	const platform = headers.get("x-surfsense-platform");
	const os = headers.get("x-surfsense-os");
	return {
		app_version: isAppVersion(version) ? version : "invalid",
		platform: isDesktopPlatform(platform) ? platform : "other",
		os: isDesktopOs(os) ? os : "other",
	};
}
