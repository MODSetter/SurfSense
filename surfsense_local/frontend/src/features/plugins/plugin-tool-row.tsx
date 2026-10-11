import { SegmentedControl } from "@/components/ui/segmented-control"
import { Switch } from "@/components/ui/switch"
import { intl } from "@/i18n/intl"

import type { Plugin, PluginTool, ToolApproval } from "./api"
import { approvalOf } from "./tool-kind"

const APPROVALS: ToolApproval[] = ["ask", "always"]

function approvalLabel(approval: ToolApproval) {
  return approval === "ask"
    ? intl.formatMessage({
        id: "plugins_tool_ask_label",
        defaultMessage: "Ask",
      })
    : intl.formatMessage({
        id: "plugins_tool_always_label",
        defaultMessage: "Always allow",
      })
}

function approvalAria(approval: ToolApproval, tool: string) {
  return approval === "ask"
    ? intl.formatMessage(
        {
          id: "plugins_tool_ask_aria",
          defaultMessage: "Ask before using {tool}",
        },
        { tool }
      )
    : intl.formatMessage(
        {
          id: "plugins_tool_always_aria",
          defaultMessage: "Always allow {tool}",
        },
        { tool }
      )
}

function Approval({
  plugin,
  tool,
  label,
  onApproval,
}: {
  plugin: Plugin
  tool: PluginTool
  label: string
  onApproval: (approval: ToolApproval) => void
}) {
  const kind = approvalOf(plugin, tool)
  if (kind !== "setting") {
    return (
      <span className="text-xs text-muted-foreground">
        {kind === "always_asks"
          ? intl.formatMessage({
              id: "plugins_tool_always_asks_label",
              defaultMessage: "Always asks",
            })
          : intl.formatMessage({
              id: "plugins_tool_never_asks_label",
              defaultMessage: "Doesn’t ask",
            })}
      </span>
    )
  }
  return (
    <SegmentedControl
      count={APPROVALS.length}
      selectedIndex={APPROVALS.indexOf(tool.approval)}
      role="radiogroup"
      aria-label={intl.formatMessage(
        {
          id: "plugins_tool_approval_aria",
          defaultMessage: "Approval for {tool}",
        },
        { tool: label }
      )}
    >
      {APPROVALS.map((approval) => (
        <label key={approval} className="relative cursor-pointer">
          <input
            type="radio"
            name={`${plugin.id}-${tool.name}-approval`}
            value={approval}
            checked={tool.approval === approval}
            className="peer sr-only"
            aria-label={approvalAria(approval, label)}
            onChange={() => onApproval(approval)}
          />
          <span className="relative flex h-7 items-center rounded-md px-2.5 text-xs peer-focus-visible:z-10 peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:outline-none">
            {approvalLabel(approval)}
          </span>
        </label>
      ))}
    </SegmentedControl>
  )
}

/** One tool: what it does, whether the agent may use it, and whether it asks first. */
export function PluginToolRow({
  plugin,
  tool,
  onEnabled,
  onApproval,
}: {
  plugin: Plugin
  tool: PluginTool
  onEnabled: (enabled: boolean) => void
  onApproval: (approval: ToolApproval) => void
}) {
  const label = tool.title ?? tool.name
  return (
    <li className="flex items-center justify-between gap-6 py-2.5">
      <div className="min-w-0">
        <p className="truncate text-sm">{label}</p>
        <p className="line-clamp-2 text-xs text-pretty text-muted-foreground">
          {tool.description}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-4">
        <Approval
          plugin={plugin}
          tool={tool}
          label={label}
          onApproval={onApproval}
        />
        <Switch
          checked={tool.enabled}
          onCheckedChange={onEnabled}
          aria-label={intl.formatMessage(
            { id: "plugins_tool_use_aria", defaultMessage: "Use {tool}" },
            { tool: label }
          )}
        />
      </div>
    </li>
  )
}
