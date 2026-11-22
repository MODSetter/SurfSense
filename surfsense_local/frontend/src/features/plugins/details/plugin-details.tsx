import { Button } from "@/components/ui/button"
import { ArrowLeftIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { Plugin } from "../api"
import { PluginDetailsCard } from "./plugin-details-card"
import { usePluginChanges } from "./use-plugin-changes"

/** One connected plugin, shown in place of the list until Back. */
export function PluginDetails({
  plugin,
  thirdPartyAllowed,
  onBack,
  onOpenLicense,
}: {
  plugin: Plugin
  thirdPartyAllowed: boolean
  onBack: () => void
  onOpenLicense?: () => void
}) {
  const changes = usePluginChanges()
  return (
    <div className="flex flex-col gap-3">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="-ml-2 self-start text-muted-foreground"
        onClick={onBack}
      >
        <ArrowLeftIcon data-icon="inline-start" />
        {intl.formatMessage({
          id: "plugins_details_back_button",
          defaultMessage: "Back",
        })}
      </Button>
      <PluginDetailsCard
        plugin={plugin}
        thirdPartyAllowed={thirdPartyAllowed}
        disconnecting={changes.disconnect.isPending}
        removing={changes.remove.isPending}
        checking={changes.check.isPending}
        onCheck={() => changes.check.mutate(plugin.id)}
        onTool={(tool, change) =>
          changes.tool.mutate({ plugin: plugin.id, tool, change })
        }
        onDisconnect={() => changes.disconnect.mutate(plugin.id)}
        onRemove={() => changes.remove.mutate(plugin.id)}
        onOpenLicense={onOpenLicense}
      />
    </div>
  )
}
