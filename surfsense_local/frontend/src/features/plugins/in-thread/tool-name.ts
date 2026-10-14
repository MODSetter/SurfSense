// opencode's MCP client keeps these in a server's and a tool's names, and turns
// anything else into "_" (its 1.18.34 build).
function clean(name: string) {
  return name.replace(/[^a-zA-Z0-9_-]/g, "_")
}

/** The name opencode, and so a step or a mention, gives a plugin's tool. */
export function opencodeToolName(pluginId: string, tool: string) {
  return `${clean(pluginId)}_${clean(tool)}`
}
