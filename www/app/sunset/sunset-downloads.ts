import type { InstallerPlatform } from "@/features/downloads/app-release";

/**
 * The sunset page's download buttons, one per installer `/downloads/<platform>` serves.
 * Absolute, so the browser the legacy app hands them to opens them on www whatever page
 * they came from. `src=legacy` counts the moves from the old app.
 */

const SITE = "https://www.surfsense.com";

const LABELS: Record<InstallerPlatform, string> = {
	windows: "Windows",
	mac: "macOS (Apple Silicon)",
	"linux-appimage": "Linux (AppImage)",
	"linux-deb": "Linux (deb)",
	"linux-rpm": "Linux (rpm)",
};

export const SUNSET_DOWNLOADS = (Object.keys(LABELS) as InstallerPlatform[]).map((platform) => ({
	platform,
	label: LABELS[platform],
	href: `${SITE}/downloads/${platform}?src=legacy`,
}));

export const SUNSET_OTHER_DOWNLOADS_URL = `${SITE}/downloads`;
