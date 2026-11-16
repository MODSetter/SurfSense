import type { Plugin, PluginTool, ToolChange } from "../api"
import { approvalOf } from "./tool-kind"

/** The one choice a tool row offers, over the stored `enabled` and `approval`. */
export type ToolPermission = "allow" | "ask" | "block"

export const PERMISSIONS: ToolPermission[] = ["allow", "ask", "block"]

export function permissionOf(plugin: Plugin, tool: PluginTool): ToolPermission {
  if (!tool.enabled) return "block"
  const kind = approvalOf(plugin, tool)
  if (kind === "always_asks") return "ask"
  if (kind === "never_asks") return "allow"
  return tool.approval === "always" ? "allow" : "ask"
}

/** The approval rules leave some tools no say in asking; block is always open. */
export function canPick(
  plugin: Plugin,
  tool: PluginTool,
  permission: ToolPermission
) {
  const kind = approvalOf(plugin, tool)
  if (permission === "allow") return kind !== "always_asks"
  if (permission === "ask") return kind !== "never_asks"
  return true
}

export function changeFor(
  plugin: Plugin,
  tool: PluginTool,
  permission: ToolPermission
): ToolChange {
  if (permission === "block") return { enabled: false }
  if (approvalOf(plugin, tool) !== "setting") return { enabled: true }
  return {
    enabled: true,
    approval: permission === "allow" ? "always" : "ask",
  }
}

/** The group's own choice when every tool shares it; null when they differ. */
export function groupPermission(plugin: Plugin, tools: PluginTool[]) {
  const picks = new Set(tools.map((tool) => permissionOf(plugin, tool)))
  return picks.size === 1 ? [...picks][0] : null
}
