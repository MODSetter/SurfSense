import type { PluginListing } from "./plugin-listing";

/**
 * SurfSense's own free plugins are part of the desktop app once the scrapers retire: nothing
 * to connect and no key, and the host their list entry still carries is not where the app's
 * calls go, so their page names neither.
 */
export function isBuiltIn(plugin: PluginListing): boolean {
	return plugin.publisher === "surfsense" && plugin.access === "free";
}

export const BUILT_IN_LABEL = "Free, built into the app";
