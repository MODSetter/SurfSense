import { useId, useState } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import type { Plugin, PluginTool, ToolApproval } from "../api"
import { ConnectPluginButton } from "./connect-plugin-button"
import { DisconnectPluginButton } from "./disconnect-plugin-button"
import { PluginIcon } from "../plugin-icon"
import { pluginTypeLabel } from "../yours/plugin-type-label"
import { PluginActionsMenu } from "./plugin-actions-menu"
import { PluginToolRow } from "./plugin-tool-row"
import { RemovePluginDialog } from "./remove-plugin-dialog"
import { ReplaceKeyButton } from "./replace-key-button"
import { SignInAgainButton } from "../sign-in/sign-in-again-button"
import { isReadOnly } from "./tool-kind"

function ToolGroup({
  plugin,
  label,
  tools,
  onTool,
}: {
  plugin: Plugin
  label: string
  tools: PluginTool[]
  onTool: (
    tool: string,
    change: { enabled: boolean } | { approval: ToolApproval }
  ) => void
}) {
  const labelId = useId()
  if (tools.length === 0) return null
  return (
    <div role="group" aria-labelledby={labelId} className="mt-5">
      <p id={labelId} className="text-xs font-medium text-muted-foreground">
        {label}
      </p>
      <ul className="divide-y">
        {tools.map((tool) => (
          <PluginToolRow
            key={tool.name}
            plugin={plugin}
            tool={tool}
            onEnabled={(enabled) => onTool(tool.name, { enabled })}
            onApproval={(approval) => onTool(tool.name, { approval })}
          />
        ))}
      </ul>
    </div>
  )
}

function checkLabel(plugin: Plugin) {
  if (plugin.check_failure === "unreachable") {
    return intl.formatMessage({
      id: "plugins_row_unreachable_status",
      defaultMessage: "Couldn’t connect",
    })
  }
  if (plugin.check_failure === "sign_in" && plugin.auth_type === "oauth") {
    return intl.formatMessage({
      id: "plugins_row_signed_out_status",
      defaultMessage: "Signed out",
    })
  }
  if (plugin.check_failure === "sign_in") {
    return intl.formatMessage({
      id: "plugins_row_sign_in_status",
      defaultMessage: "Needs a new key",
    })
  }
  if (plugin.check_failure === "needs_license") {
    return intl.formatMessage({
      id: "plugins_row_needs_license_status",
      defaultMessage: "Needs a license",
    })
  }
  if (plugin.check_failure === "license_expired") {
    return intl.formatMessage({
      id: "plugins_row_license_expired_status",
      defaultMessage: "License expired",
    })
  }
  if (plugin.check_failure === "license_revoked") {
    return intl.formatMessage({
      id: "plugins_row_license_revoked_status",
      defaultMessage: "License revoked",
    })
  }
  if (plugin.check_failure === "license_invalid") {
    return intl.formatMessage({
      id: "plugins_row_license_invalid_status",
      defaultMessage: "License not recognized",
    })
  }
  if (!plugin.enabled) {
    return intl.formatMessage({
      id: "plugins_row_paused_status",
      defaultMessage: "Paused",
    })
  }
  return intl.formatMessage({
    id: "plugins_row_connected_status",
    defaultMessage: "Connected",
  })
}

const LICENSE_FAILURES = new Set<Plugin["check_failure"]>([
  "needs_license",
  "license_expired",
  "license_revoked",
  "license_invalid",
])

/** A plugin's details: Disconnect or Connect, the rest in a menu, then its status and tools. */
export function PluginDetailsCard({
  plugin,
  thirdPartyAllowed,
  disconnecting,
  removing,
  checking,
  onCheck,
  onEnabled,
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
  onEnabled: (enabled: boolean) => void
  onTool: (
    tool: string,
    change: { enabled: boolean } | { approval: ToolApproval }
  ) => void
  onDisconnect: () => void
  onRemove: () => void
  onOpenLicense?: () => void
}) {
  const nameId = useId()
  const [removeOpen, setRemoveOpen] = useState(false)
  const unused = plugin.source !== "first_party" && !thirdPartyAllowed
  return (
    <section aria-labelledby={nameId}>
      <div className="flex items-center justify-between gap-6">
        <div className="flex min-w-0 items-center gap-3">
          <PluginIcon
            id={plugin.id}
            name={plugin.name}
            hasIcon={plugin.source === "registry"}
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
          {plugin.disconnected ? (
            <ConnectPluginButton plugin={plugin} size="sm" />
          ) : (
            <DisconnectPluginButton
              name={plugin.name}
              disconnecting={disconnecting}
              onDisconnect={onDisconnect}
            />
          )}
          <PluginActionsMenu
            plugin={plugin}
            checking={checking}
            onCheck={onCheck}
            onEnabled={onEnabled}
            onRemove={() => setRemoveOpen(true)}
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
      {plugin.disconnected ? (
        <p className="mt-4 text-xs text-muted-foreground">
          {intl.formatMessage({
            id: "plugins_row_disconnected_status",
            defaultMessage: "Disconnected",
          })}
        </p>
      ) : (
        <div className="mt-4 flex items-center gap-2 text-xs">
          <span
            className={
              plugin.check_failure
                ? "text-destructive"
                : "text-muted-foreground"
            }
          >
            {checkLabel(plugin)}
          </span>
          {checking ? (
            <Spinner className="size-3 text-muted-foreground" />
          ) : null}
          {plugin.check_failure === "sign_in" ? (
            plugin.auth_type === "oauth" ? (
              <SignInAgainButton plugin={plugin} />
            ) : (
              <ReplaceKeyButton plugin={plugin} />
            )
          ) : null}
          {LICENSE_FAILURES.has(plugin.check_failure) && onOpenLicense ? (
            <Button
              type="button"
              size="xs"
              variant="ghost"
              onClick={onOpenLicense}
            >
              {intl.formatMessage({
                id: "plugins_row_license_settings_button",
                defaultMessage: "License settings",
              })}
            </Button>
          ) : null}
        </div>
      )}
      {plugin.tools.some((tool) => tool.change) ? (
        <p className="mt-2 text-xs text-muted-foreground">
          {intl.formatMessage({
            id: "plugins_row_changed_tools_body",
            defaultMessage:
              "Some tools are new or changed. They stay off until you allow them.",
          })}
        </p>
      ) : null}
      {plugin.removed_reason ? (
        <p className="mt-2 text-xs text-destructive">
          {intl.formatMessage(
            {
              id: "plugins_row_removed_body",
              defaultMessage: "No longer listed: {reason}",
            },
            { reason: plugin.removed_reason }
          )}
        </p>
      ) : null}
      {unused ? (
        <p className="mt-2 text-xs text-muted-foreground">
          {intl.formatMessage({
            id: "plugins_row_third_party_off_body",
            defaultMessage: "Not used until third-party plugins are allowed",
          })}
        </p>
      ) : null}
      {plugin.tools.length === 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">
          {intl.formatMessage({
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
    </section>
  )
}
