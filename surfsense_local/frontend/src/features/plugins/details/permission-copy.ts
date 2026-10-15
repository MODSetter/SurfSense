import { BanIcon, CheckCircle2Icon, HandIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { ToolPermission } from "./tool-permission"

export const PERMISSION_ICON = {
  allow: CheckCircle2Icon,
  ask: HandIcon,
  block: BanIcon,
} as const

export function permissionTitle(permission: ToolPermission) {
  if (permission === "allow") {
    return intl.formatMessage({
      id: "plugins_permission_allow_title",
      defaultMessage: "Always allowed",
    })
  }
  if (permission === "ask") {
    return intl.formatMessage({
      id: "plugins_permission_ask_title",
      defaultMessage: "Needs approval",
    })
  }
  return intl.formatMessage({
    id: "plugins_permission_block_title",
    defaultMessage: "Blocked",
  })
}

/** What the choice does, or why the approval rules leave it closed for this tool. */
export function permissionBody(permission: ToolPermission, open: boolean) {
  if (permission === "allow") {
    return open
      ? intl.formatMessage({
          id: "plugins_permission_allow_body",
          defaultMessage: "The agent uses it without asking",
        })
      : intl.formatMessage({
          id: "plugins_permission_allow_closed_body",
          defaultMessage:
            "Not available: the server doesn’t say this tool is safe",
        })
  }
  if (permission === "ask") {
    return open
      ? intl.formatMessage({
          id: "plugins_permission_ask_body",
          defaultMessage: "The agent asks before each use",
        })
      : intl.formatMessage({
          id: "plugins_permission_ask_closed_body",
          defaultMessage: "Not needed: this tool only reads",
        })
  }
  return intl.formatMessage({
    id: "plugins_permission_block_body",
    defaultMessage: "The agent can’t see or use it",
  })
}

export function permissionAria(permission: ToolPermission, tool: string) {
  if (permission === "allow") {
    return intl.formatMessage(
      { id: "plugins_tool_always_aria", defaultMessage: "Always allow {tool}" },
      { tool }
    )
  }
  if (permission === "ask") {
    return intl.formatMessage(
      {
        id: "plugins_tool_ask_aria",
        defaultMessage: "Ask before using {tool}",
      },
      { tool }
    )
  }
  return intl.formatMessage(
    { id: "plugins_tool_block_aria", defaultMessage: "Block {tool}" },
    { tool }
  )
}

/** The group menu's words: the state every tool in it shares. */
export function groupStateLabel(permission: ToolPermission) {
  if (permission === "allow") {
    return intl.formatMessage({
      id: "plugins_group_allow_label",
      defaultMessage: "Always allow",
    })
  }
  if (permission === "ask") {
    return intl.formatMessage({
      id: "plugins_group_needs_approval_label",
      defaultMessage: "Needs approval",
    })
  }
  return intl.formatMessage({
    id: "plugins_group_blocked_label",
    defaultMessage: "Blocked",
  })
}
