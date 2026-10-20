import { useQuery, type UseQueryResult } from "@tanstack/react-query"
import { useEffect } from "react"

import { Skeleton } from "@/components/ui/skeleton"
import { intl } from "@/i18n/intl"

import { thirdPartyAllowed, thirdPartyQueryKey, type Plugin } from "../api"
import { ConnectedPluginsTable } from "./connected-plugins-table"
import { NoPluginsConnected } from "./no-plugins-connected"
import { PluginDetails } from "../details/plugin-details"

/** The plugins the user connected: a list, or one plugin's details. */
export function YourPlugins({
  plugins,
  openId,
  onOpenIdChange: setOpenId,
  onBrowse,
  onAdd,
  onOpenLicense,
}: {
  plugins: UseQueryResult<Plugin[]>
  /** The plugin whose details show, held above so a plugin just added can open. */
  openId: string | null
  onOpenIdChange: (id: string | null) => void
  onBrowse: () => void
  onAdd: () => void
  onOpenLicense?: () => void
}) {
  const thirdParty = useQuery({
    queryKey: thirdPartyQueryKey,
    queryFn: ({ signal }) => thirdPartyAllowed(signal),
  })
  // A plugin removed while open is gone from the list, which shows again.
  const open = plugins.data?.find((plugin) => plugin.id === openId)
  const gone = openId !== null && plugins.data !== undefined && !open
  useEffect(() => {
    if (gone) setOpenId(null)
  }, [gone, setOpenId])
  if (plugins.isLoading) return <Skeleton className="h-24 w-full" />
  if (plugins.error) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {intl.formatMessage({
          id: "plugins_settings_load_error",
          defaultMessage: "Couldn’t load plugins.",
        })}
      </p>
    )
  }
  const allowed = thirdParty.data ?? false
  if (open) {
    return (
      <PluginDetails
        plugin={open}
        thirdPartyAllowed={allowed}
        onBack={() => setOpenId(null)}
        onOpenLicense={onOpenLicense}
      />
    )
  }
  if (!plugins.data?.length) {
    return <NoPluginsConnected onBrowse={onBrowse} onAdd={onAdd} />
  }
  return (
    <ConnectedPluginsTable
      plugins={plugins.data}
      thirdPartyAllowed={allowed}
      onOpen={setOpenId}
    />
  )
}
