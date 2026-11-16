import { useId, useState } from "react"

import { intl } from "@/i18n/intl"

import type { Plugin, ToolChange } from "../api"
import { PluginIcon } from "../plugin-icon"
import { thirdPartyHeld } from "../third-party-held"
import { pluginTypeLabel } from "../yours/plugin-type-label"
import { PluginActionsMenu } from "./plugin-actions-menu"
import { PluginMainAction } from "./plugin-main-action"
import { PluginStatusLine } from "./plugin-status-line"
import { RemovePluginDialog } from "./remove-plugin-dialog"
import { isReadOnly } from "./tool-kind"
import { ToolGroup } from "./tool-group"

/** A plugin's details: Connect or Disconnect, the rest in a menu, then its status and tools. */
export function PluginDetailsCard({
  plugin,
  thirdPartyAllowed,
  disconnecting,
  removing,
  checking,
  onCheck,
  onTool,
  onDisconnect,
  onRemove,
  onOpenLicense,
}: {
  plugin: Plugin
  thirdPartyAllowed: boolean
  disconnecting: boolean
  removing: boolean
  checking: boolean
  onCheck: () => void
  onTool: (tool: string, change: ToolChange) => void
  onDisconnect: () => void
  onRemove: () => void
  onOpenLicense?: () => void
}) {
  const nameId = useId()
  const [removeOpen, setRemoveOpen] = useState(false)
  const unused = thirdPartyHeld(plugin, thirdPartyAllowed)
  return (
    <section aria-labelledby={nameId}>
      <div className="flex items-center justify-between gap-6">
        <div className="flex min-w-0 items-center gap-3">
          <PluginIcon
            id={plugin.id}
            name={plugin.name}
            hasIcon={plugin.source !== "custom"}
            firstParty={plugin.source === "first_party"}
            // As tall as the name and type beside it.
            className="size-11 rounded-lg text-base"
          />
          <div className="min-w-0">
            <h3 id={nameId} className="truncate text-base font-medium">
              {plugin.name}
            </h3>
            <p className="truncate text-xs text-muted-foreground">
              {pluginTypeLabel(plugin.source)}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <PluginMainAction
            plugin={plugin}
            thirdPartyAllowed={thirdPartyAllowed}
            disconnecting={disconnecting}
            onDisconnect={onDisconnect}
          />
          <PluginActionsMenu
            plugin={plugin}
            held={unused}
            checking={checking}
            onCheck={onCheck}
            onRemove={() => setRemoveOpen(true)}
            onOpenLicense={onOpenLicense}
          />
          <RemovePluginDialog
            name={plugin.name}
            open={removeOpen}
            onOpenChange={setRemoveOpen}
            removing={removing}
            onRemove={onRemove}
          />
        </div>
      </div>
      <PluginStatusLine plugin={plugin} unused={unused} checking={checking} />
      {/* Its tools, and what to know about them, apart from its state. */}
      <div className="mt-6">
        {plugin.tools.some((tool) => tool.change) ? (
          <p className="text-xs text-muted-foreground">
            {intl.formatMessage({
              id: "plugins_row_changed_tools_body",
              defaultMessage:
                "Some tools are new or changed. They stay off until you allow them.",
            })}
          </p>
        ) : null}
        {/* Held by the third-party switch, it lists nothing; its status says why. */}
        {plugin.tools.length === 0 && !unused ? (
          <p className="text-xs text-muted-foreground">
            {plugin.check_failure === "sign_in" && plugin.never_signed_in
              ? intl.formatMessage({
                  id: "plugins_row_connect_for_tools_empty",
                  defaultMessage: "Connect to see its tools.",
                })
              : plugin.check_failure === "sign_in"
                ? // Its tools are listed with the token a sign-in gives.
                  intl.formatMessage({
                    id: "plugins_row_sign_in_for_tools_empty",
                    defaultMessage: "Sign in to see its tools.",
                  })
                : intl.formatMessage({
                    id: "plugins_row_no_tools_empty",
                    defaultMessage: "This server lists no tools.",
                  })}
          </p>
        ) : null}
        <ToolGroup
          plugin={plugin}
          label={intl.formatMessage({
            id: "plugins_row_read_only_label",
            defaultMessage: "Read-only",
          })}
          tools={plugin.tools.filter(isReadOnly)}
          onTool={onTool}
        />
        <ToolGroup
          plugin={plugin}
          label={intl.formatMessage({
            id: "plugins_row_can_change_label",
            defaultMessage: "Can make changes",
          })}
          tools={plugin.tools.filter((tool) => !isReadOnly(tool))}
          onTool={onTool}
        />
      </div>
    </section>
  )
}
