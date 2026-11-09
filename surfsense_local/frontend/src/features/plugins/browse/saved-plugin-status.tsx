import { useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import {
  listPlugins,
  pluginsQueryKey,
  thirdPartyAllowed,
  thirdPartyQueryKey,
} from "../api"
import { useOpenPlugin } from "../open-plugin"
import { pluginStatus } from "../yours/plugin-status"
import { TONE_CLASS } from "../yours/status-tone"

/** A listed plugin already saved: its state as Yours shows it, opening its details there. */
export function SavedPluginStatus({ pluginId }: { pluginId: string }) {
  const openPlugin = useOpenPlugin()
  const plugins = useQuery({
    queryKey: pluginsQueryKey,
    queryFn: ({ signal }) => listPlugins(signal),
  })
  const thirdParty = useQuery({
    queryKey: thirdPartyQueryKey,
    queryFn: ({ signal }) => thirdPartyAllowed(signal),
  })
  const plugin = plugins.data?.find((saved) => saved.id === pluginId)
  // Saved a moment ago, before the list caught up.
  if (!plugin) {
    return (
      <span className="text-xs text-muted-foreground">
        {intl.formatMessage({
          id: "plugins_listed_connected_status",
          defaultMessage: "Connected",
        })}
      </span>
    )
  }
  const status = pluginStatus(plugin, thirdParty.data ?? false)
  return (
    <Button
      type="button"
      variant="bare"
      className={cn("text-xs hover:underline", TONE_CLASS[status.tone])}
      onClick={() => openPlugin(plugin.id)}
    >
      {status.label}
    </Button>
  )
}
