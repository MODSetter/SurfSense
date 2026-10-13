import type { FirstPartyEntry, Plugin, RegistryEntry } from "../api"

/** A plugin as one of the two lists describes it: SurfSense's own, or the registry's. */
export type ListedEntry = FirstPartyEntry | RegistryEntry

// Only a registry entry names its publisher; every first-party entry is SurfSense's.
export function isRegistryEntry(entry: ListedEntry): entry is RegistryEntry {
  return "publisher" in entry
}

/** How the plugin signs in, as its page and its Connect read it. */
export function entryNeeds(entry: ListedEntry): Plugin["auth_type"] {
  if (isRegistryEntry(entry)) return entry.auth_type
  return entry.access === "license" ? "license" : "none"
}
