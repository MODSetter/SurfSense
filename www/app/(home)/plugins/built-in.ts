import type { PluginListing } from "./plugin-listing";

/** Reading pages, YouTube and search are part of the app: nothing to connect, no key, no host. */
export function isBuiltIn(plugin: PluginListing): boolean {
	return plugin.builtIn === true;
}

export const BUILT_IN_LABEL = "Free, built into the app";
