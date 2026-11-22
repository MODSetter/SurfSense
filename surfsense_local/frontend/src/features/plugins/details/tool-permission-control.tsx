import { SegmentedControl } from "@/components/ui/segmented-control"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { Plugin, PluginTool } from "../api"
import {
  PERMISSION_ICON,
  permissionAria,
  permissionBody,
  permissionTitle,
} from "./permission-copy"
import {
  PERMISSIONS,
  canPick,
  permissionOf,
  type ToolPermission,
} from "./tool-permission"

/** Allow, ask or block as three icons; each says in a tooltip what it does, or why it is closed. */
export function ToolPermissionControl({
  plugin,
  tool,
  label,
  onPick,
}: {
  plugin: Plugin
  tool: PluginTool
  label: string
  onPick: (permission: ToolPermission) => void
}) {
  const current = permissionOf(plugin, tool)
  return (
    <SegmentedControl
      count={PERMISSIONS.length}
      selectedIndex={PERMISSIONS.indexOf(current)}
      role="radiogroup"
      aria-label={intl.formatMessage(
        {
          id: "plugins_tool_permission_aria",
          defaultMessage: "Permission for {tool}",
        },
        { tool: label }
      )}
      className="shrink-0"
    >
      {PERMISSIONS.map((permission) => {
        const open = canPick(plugin, tool, permission)
        const Icon = PERMISSION_ICON[permission]
        return (
          <Tooltip key={permission}>
            <TooltipTrigger
              render={
                <label
                  className={cn(
                    "relative",
                    open ? "cursor-pointer" : "cursor-not-allowed opacity-40"
                  )}
                />
              }
            >
              <input
                type="radio"
                name={`${plugin.id}-${tool.name}-permission`}
                value={permission}
                checked={current === permission}
                disabled={!open}
                className="peer sr-only"
                aria-label={permissionAria(permission, label)}
                onChange={() => onPick(permission)}
              />
              <span className="relative flex size-7 items-center justify-center rounded-md peer-focus-visible:z-10 peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:outline-none">
                <Icon className="size-4" />
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-64 font-normal">
              <p className="font-medium">{permissionTitle(permission)}</p>
              <p className="text-muted-foreground">
                {permissionBody(permission, open)}
              </p>
            </TooltipContent>
          </Tooltip>
        )
      })}
    </SegmentedControl>
  )
}
