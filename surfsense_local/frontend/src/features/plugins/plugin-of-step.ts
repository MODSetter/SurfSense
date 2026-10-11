import { useQuery } from "@tanstack/react-query"

import {
  listPlugins,
  pluginsQueryKey,
  type Plugin,
  type PluginTool,
} from "./api"

// opencode's MCP client keeps these in a server's and a tool's names, and turns
// anything else into "_"; SurfSense's own server is never a plugin.
function clean(name: string) {
  return name.replace(/[^a-zA-Z0-9_-]/g, "_")
}

/** Whether opencode's name for a step could be a plugin's `<plugin>_<tool>`. */
export function mayBePluginStep(tool: string | null) {
  return tool !== null && tool.includes("_") && !tool.startsWith("surfsense_")
}

/** The connected plugin and tool a step called, or null once it is disconnected. */
export function usePluginOfStep(
  tool: string | null
): { plugin: Plugin; tool: PluginTool } | null {
  const plugins = useQuery({
    queryKey: pluginsQueryKey,
    queryFn: ({ signal }) => listPlugins(signal),
    enabled: mayBePluginStep(tool),
    staleTime: 60_000,
  })
  for (const plugin of plugins.data ?? []) {
    for (const row of plugin.tools) {
      if (`${clean(plugin.id)}_${clean(row.name)}` === tool) {
        return { plugin, tool: row }
      }
    }
  }
  return null
}
