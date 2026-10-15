import { useId, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { ChevronDownIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { Plugin, PluginTool, ToolChange } from "../api"
import { GroupPermissionMenu } from "./group-permission-menu"
import { PluginToolRow } from "./plugin-tool-row"
import {
  canPick,
  changeFor,
  groupPermission,
  permissionOf,
  type ToolPermission,
} from "./tool-permission"

/** Read-only or Can make changes: folds away, and its menu sets every tool in it. */
export function ToolGroup({
  plugin,
  label,
  tools,
  onTool,
}: {
  plugin: Plugin
  label: string
  tools: PluginTool[]
  onTool: (tool: string, change: ToolChange) => void
}) {
  const labelId = useId()
  const listId = useId()
  const [open, setOpen] = useState(true)
  if (tools.length === 0) return null

  const pickAll = (permission: ToolPermission) => {
    for (const tool of tools) {
      // A tool the rules hold to asking, or to never asking, only needs switching on.
      const unchanged = canPick(plugin, tool, permission)
        ? permissionOf(plugin, tool) === permission
        : tool.enabled
      if (!unchanged) onTool(tool.name, changeFor(plugin, tool, permission))
    }
  }

  return (
    <div role="group" aria-labelledby={labelId} className="mt-5">
      <div className="flex items-center justify-between gap-4">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={listId}
          onClick={() => setOpen((value) => !value)}
          className="-ml-1 flex items-center gap-1.5 rounded-md px-1 py-0.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          <ChevronDownIcon
            className={cn(
              "size-4 text-muted-foreground transition-transform duration-150 motion-reduce:transition-none",
              !open && "-rotate-90"
            )}
          />
          <span id={labelId}>{label}</span>
          <Badge variant="secondary" className="tabular-nums">
            {intl.formatNumber(tools.length)}
          </Badge>
        </button>
        <GroupPermissionMenu
          group={label}
          current={groupPermission(plugin, tools)}
          onPick={pickAll}
        />
      </div>
      {open ? (
        <ul id={listId} className="mt-1 divide-y pl-6">
          {tools.map((tool) => (
            <PluginToolRow
              key={tool.name}
              plugin={plugin}
              tool={tool}
              onPick={(permission) =>
                onTool(tool.name, changeFor(plugin, tool, permission))
              }
            />
          ))}
        </ul>
      ) : null}
    </div>
  )
}
