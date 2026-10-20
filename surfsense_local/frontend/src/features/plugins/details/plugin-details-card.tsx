import { useId, useState } from "react"

import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import type { Plugin, ToolChange } from "../api"
import { PluginIcon } from "../plugin-icon"
import { pluginTypeLabel } from "../yours/plugin-type-label"
import { PluginActionsMenu } from "./plugin-actions-menu"
import { PluginMainAction } from "./plugin-main-action"
import { RemovePluginDialog } from "./remove-plugin-dialog"
import { isReadOnly } from "./tool-kind"
import { checkTone, TONE_CLASS } from "../yours/status-tone"
import { ToolGroup } from "./tool-group"

function checkLabel(plugin: Plugin) {
  if (plugin.check_failure === "sign_in" && plugin.needs_own_app) {
    return intl.formatMessage({
      id: "plugins_row_needs_own_app_status",
      defaultMessage: "Needs an OAuth app",
    })
  }
  if (plugin.check_failure === "sign_in" && plugin.never_signed_in) {
    return intl.formatMessage({
      id: "plugins_row_not_connected_status",
      defaultMessage: "Not connected",
    })
  }
  if (plugin.check_failure === "unreachable") {
    return intl.formatMessage({
      id: "plugins_row_unreachable_status",
      defaultMessage: "Couldn’t connect",
    })
  }
  if (plugin.check_failure === "sign_in" && plugin.needs_scopes.length) {
    return intl.formatMessage({
      id: "plugins_row_needs_scopes_status",
      defaultMessage: "Needs more access",
    })
  }
  if (plugin.check_failure === "sign_in" && plugin.auth_type === "oauth") {
    return intl.formatMessage({
      id: "plugins_row_needs_sign_in_status",
      defaultMessage: "Needs sign-in",
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
      defaultMessage: "Off",
    })
  }
  return intl.formatMessage({
    id: "plugins_row_connected_status",
    defaultMessage: "Connected",
  })
}

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
  const unused = plugin.source !== "first_party" && !thirdPartyAllowed
  return (
    <section aria-labelledby={nameId}>
      <div className="flex items-center justify-between gap-6">
        <div className="flex min-w-0 items-center gap-3">
          <PluginIcon
            id={plugin.id}
            name={plugin.name}
            hasIcon={plugin.source !== "custom"}
            firstParty={plugin.source === "first_party"}
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
            disconnecting={disconnecting}
            onDisconnect={onDisconnect}
          />
          <PluginActionsMenu
            plugin={plugin}
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
                ? TONE_CLASS[checkTone(plugin)]
                : "text-muted-foreground"
            }
          >
            {checkLabel(plugin)}
          </span>
          {checking ? (
            <Spinner className="size-3 text-muted-foreground" />
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
      {plugin.needs_own_app && plugin.check_failure === "sign_in" ? (
        <p className="mt-2 text-xs text-muted-foreground">
          {plugin.needs_own_app === "refused"
            ? intl.formatMessage(
                {
                  id: "plugins_row_own_app_refused_body",
                  defaultMessage:
                    "{plugin} refused to register SurfSense; it may accept only apps it approved.",
                },
                { plugin: plugin.name }
              )
            : intl.formatMessage(
                {
                  id: "plugins_row_own_app_needs_client_body",
                  defaultMessage:
                    "{plugin} accepts only apps registered with it.",
                },
                { plugin: plugin.name }
              )}
        </p>
      ) : null}
      {plugin.removed_reason ? (
        <p className="mt-2 text-xs text-warning">
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
    </section>
  )
}
