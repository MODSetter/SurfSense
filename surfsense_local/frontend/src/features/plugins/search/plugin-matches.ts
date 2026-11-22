import type { FirstPartyEntry, Plugin, RegistryEntry } from "../api"

/** Every word of the query appears somewhere in what is said of the plugin, in any order. */
export function matchesQuery(
  query: string,
  fields: (string | null | undefined)[]
): boolean {
  const said = fields.filter(Boolean).join(" ").toLocaleLowerCase()
  return query
    .toLocaleLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => said.includes(word))
}

/** A connected plugin has no description, so its tools and host say what it is. */
export function connectedFields(plugin: Plugin) {
  return [
    plugin.name,
    plugin.id,
    ...plugin.hosts,
    ...plugin.tools.flatMap((tool) => [tool.name, tool.title]),
  ]
}

export function listedFields(entry: FirstPartyEntry | RegistryEntry) {
  return [
    entry.name,
    entry.id,
    entry.description,
    entry.author,
    ...(entry.tools ?? []),
  ]
}
