import { useId, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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

  // A tool the approval rules keep from this choice stays as it is: switching it
  // on could leave it asking less than the choice says.
  const pickAll = (permission: ToolPermission) => {
    for (const tool of tools) {
      if (!canPick(plugin, tool, permission)) continue
      if (permissionOf(plugin, tool) === permission) continue
      onTool(tool.name, changeFor(plugin, tool, permission))
    }
  }

  return (
    <div role="group" aria-labelledby={labelId} className="mt-5">
      <div className="flex items-center justify-between gap-4">
        <Button
          type="button"
          variant="bare"
          aria-expanded={open}
          aria-controls={listId}
          onClick={() => setOpen((value) => !value)}
          className="-ml-1 flex items-center gap-1.5 rounded-md px-1 py-0.5 text-sm font-medium focus-visible:ring-2"
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
        </Button>
        <GroupPermissionMenu
          group={label}
          current={groupPermission(plugin, tools)}
          canTake={(permission) =>
            tools.some((tool) => canPick(plugin, tool, permission))
          }
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
