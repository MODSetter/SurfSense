import { Badge } from "@/components/ui/badge"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { Plugin, PluginTool } from "../api"
import { ToolPermissionControl } from "./tool-permission-control"
import type { ToolPermission } from "./tool-permission"

/** One tool: its name and whether the agent may use it. */
export function PluginToolRow({
  plugin,
  tool,
  onPick,
}: {
  plugin: Plugin
  tool: PluginTool
  onPick: (permission: ToolPermission) => void
}) {
  const label = tool.title ?? tool.name
  return (
    <li className="flex items-center justify-between gap-6 py-2">
      <p
        className={cn(
          "flex min-w-0 items-center gap-2 text-sm transition-colors",
          // A blocked tool is out of the agent's reach: its name steps back.
          !tool.enabled && "text-muted-foreground"
        )}
      >
        <span className="truncate">{label}</span>
        <span className="sr-only">{tool.description}</span>
        {tool.change ? (
          <Badge variant="secondary" className="shrink-0">
            {tool.change === "added"
              ? intl.formatMessage({
                  id: "plugins_tool_added_label",
                  defaultMessage: "New",
                })
              : intl.formatMessage({
                  id: "plugins_tool_changed_label",
                  defaultMessage: "Changed",
                })}
          </Badge>
        ) : null}
      </p>
      <ToolPermissionControl
        plugin={plugin}
        tool={tool}
        label={label}
        onPick={onPick}
      />
    </li>
  )
}
