import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { PlusIcon } from "@/components/ui/icons"
import { Skeleton } from "@/components/ui/skeleton"
import { SettingsSection } from "@/features/settings/settings-section"
import { intl } from "@/i18n/intl"

import {
  listPlugins,
  pluginsQueryKey,
  thirdPartyAllowed,
  thirdPartyQueryKey,
} from "./api"
import { AddPluginDialog } from "./add-plugin-dialog"
import { FirstPartyPlugins } from "./first-party-plugins"
import { PluginRow } from "./plugin-row"
import { RegistryPlugins } from "./registry-plugins"
import { ThirdPartySwitch } from "./third-party-switch"
import { usePluginChanges } from "./use-plugin-changes"

export function PluginsSettings({
  onOpenLicense,
}: {
  /** Shown on a plugin whose license was refused. */
  onOpenLicense?: () => void
}) {
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)
  const plugins = useQuery({
    queryKey: pluginsQueryKey,
    queryFn: ({ signal }) => listPlugins(signal),
  })
  const thirdParty = useQuery({
    queryKey: thirdPartyQueryKey,
    queryFn: ({ signal }) => thirdPartyAllowed(signal),
  })
  const changes = usePluginChanges()

  return (
    <SettingsSection
      title={intl.formatMessage({
        id: "plugins_settings_title",
        defaultMessage: "Plugins",
      })}
      description={intl.formatMessage({
        id: "plugins_settings_body",
        defaultMessage:
          "Tools from MCP servers that the agent can use. Plugins work in Agentic threads.",
      })}
    >
      <FirstPartyPlugins />
      <ThirdPartySwitch
        allowed={thirdParty.data ?? false}
        onChange={(allowed) => changes.thirdParty.mutate(allowed)}
      />
      <RegistryPlugins allowed={thirdParty.data ?? false} />
      <div className="mt-8 mb-3 flex items-center justify-between gap-4">
        <h3 className="text-sm font-medium">
          {intl.formatMessage({
            id: "plugins_settings_servers_title",
            defaultMessage: "MCP servers",
          })}
        </h3>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setAdding(true)}
        >
          <PlusIcon data-icon="inline-start" />
          {intl.formatMessage({
            id: "plugins_settings_add_button",
            defaultMessage: "Add MCP server",
          })}
        </Button>
      </div>
      {plugins.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : plugins.error ? (
        <p role="alert" className="text-sm text-destructive">
          {intl.formatMessage({
            id: "plugins_settings_load_error",
            defaultMessage: "Couldn’t load plugins.",
          })}
        </p>
      ) : plugins.data?.length ? (
        <div className="flex flex-col gap-3">
          {plugins.data.map((plugin) => (
            <PluginRow
              key={plugin.id}
              plugin={plugin}
              thirdPartyAllowed={thirdParty.data ?? false}
              disconnecting={
                changes.disconnect.isPending &&
                changes.disconnect.variables === plugin.id
              }
              checking={
                changes.check.isPending && changes.check.variables === plugin.id
              }
              onCheck={() => changes.check.mutate(plugin.id)}
              onEnabled={(enabled) =>
                changes.plugin.mutate({ plugin: plugin.id, enabled })
              }
              onTool={(tool, change) =>
                changes.tool.mutate({ plugin: plugin.id, tool, change })
              }
              onDisconnect={() => changes.disconnect.mutate(plugin.id)}
              onOpenLicense={onOpenLicense}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          {intl.formatMessage({
            id: "plugins_settings_empty",
            defaultMessage: "No MCP servers yet. Add one by its URL.",
          })}
        </p>
      )}
      <AddPluginDialog
        open={adding}
        onOpenChange={setAdding}
        onAdded={() => {
          setAdding(false)
          void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
        }}
      />
    </SettingsSection>
  )
}
