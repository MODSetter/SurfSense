import type { Plugin, PluginTool } from "../api"

/** As the server says; a server is trusted only to describe its own tools. */
export function isReadOnly(tool: PluginTool) {
  return tool.annotations.readOnlyHint === true
}

/**
 * Mirrors the backend's approval rules (gateway/approval.py): a tool that says
 * nothing of itself may destroy, so it always asks, and a first-party
 * read-only one never does.
 */
export function approvalOf(plugin: Plugin, tool: PluginTool) {
  if (isReadOnly(tool)) {
    return plugin.source === "first_party" ? "never_asks" : "setting"
  }
  return tool.annotations.destructiveHint === false ? "setting" : "always_asks"
}
