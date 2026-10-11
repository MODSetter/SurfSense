import { useId } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { intl } from "@/i18n/intl"

import type { Plugin, PluginTool, ToolApproval } from "./api"
import { DisconnectPluginButton } from "./disconnect-plugin-button"
import { PluginToolRow } from "./plugin-tool-row"
import { ReplaceKeyButton } from "./replace-key-button"
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
    <div role="group" aria-labelledby={labelId} className="mt-3">
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

/** A connected plugin: its switch, its tools, and the way to disconnect it. */
export function PluginRow({
  plugin,
  thirdPartyAllowed,
  disconnecting,
  checking,
  onCheck,
  onEnabled,
  onTool,
  onDisconnect,
  onOpenLicense,
}: {
  plugin: Plugin
  thirdPartyAllowed: boolean
  disconnecting: boolean
  checking: boolean
  onCheck: () => void
  onEnabled: (enabled: boolean) => void
  onTool: (
    tool: string,
    change: { enabled: boolean } | { approval: ToolApproval }
  ) => void
  onDisconnect: () => void
  onOpenLicense?: () => void
}) {
  const nameId = useId()
  const host = plugin.hosts[0] ?? plugin.url
  const unused = plugin.source !== "first_party" && !thirdPartyAllowed
  return (
    <section aria-labelledby={nameId} className="rounded-xl border px-4 py-3">
      <div className="flex items-center justify-between gap-6">
        <div className="min-w-0">
          <h3 id={nameId} className="truncate text-sm font-medium">
            {plugin.name}
          </h3>
          <p className="truncate text-xs text-muted-foreground">
            {plugin.source === "first_party"
              ? intl.formatMessage(
                  {
                    id: "plugins_row_first_party_label",
                    defaultMessage: "By SurfSense · {host}",
                  },
                  { host }
                )
              : intl.formatMessage(
                  {
                    id: "plugins_row_third_party_label",
                    defaultMessage: "Third-party · {host}",
                  },
                  { host }
                )}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <DisconnectPluginButton
            name={plugin.name}
            disconnecting={disconnecting}
            onDisconnect={onDisconnect}
          />
          <Switch
            checked={plugin.enabled}
            onCheckedChange={onEnabled}
            aria-label={intl.formatMessage(
              { id: "plugins_row_use_aria", defaultMessage: "Use {plugin}" },
              { plugin: plugin.name }
            )}
          />
        </div>
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs">
        <span
          className={
            plugin.check_failure ? "text-destructive" : "text-muted-foreground"
          }
        >
          {checkLabel(plugin)}
        </span>
        {plugin.check_failure === "sign_in" ? (
          <ReplaceKeyButton plugin={plugin} />
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
        <Button
          type="button"
          size="xs"
          variant="ghost"
          disabled={checking}
          onClick={onCheck}
        >
          {checking ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "plugins_row_check_button",
            defaultMessage: "Check now",
          })}
        </Button>
      </div>
      {plugin.tools.some((tool) => tool.change) ? (
        <p className="mt-2 text-xs text-muted-foreground">
          {intl.formatMessage({
            id: "plugins_row_changed_tools_body",
            defaultMessage:
              "Some tools are new or changed. They stay off until you allow them.",
          })}
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
