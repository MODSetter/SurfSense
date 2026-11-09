import { SURFSENSE_PLUGINS } from "./plugin-list";
import type { PluginListing } from "./plugin-listing";
import { registryPlugins } from "./registry-plugins";

/** Every plugin with a page: SurfSense's own, then the registry's. Ids never clash; the registry check refuses one. */
export async function allPlugins(): Promise<PluginListing[]> {
	return [...SURFSENSE_PLUGINS, ...(await registryPlugins())];
}

export async function findPlugin(id: string): Promise<PluginListing | null> {
	return (await allPlugins()).find((plugin) => plugin.id === id) ?? null;
}
