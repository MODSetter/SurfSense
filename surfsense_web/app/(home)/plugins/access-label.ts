import type { PluginListing } from "./plugin-listing";

/** Who pays for a plugin, as its card and its page name it. */
export const ACCESS_LABEL: Record<PluginListing["access"], string> = {
	license: "SurfSense licence",
	free: "Free",
	external: "Paid by publisher",
};
