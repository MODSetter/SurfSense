import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import {
  firstPartyQueryKey,
  listFirstParty,
  listRegistry,
  registryQueryKey,
} from "../api"
import { isRegistryEntry, type ListedEntry } from "../public-page/listed-entry"
import { PluginPublicPage } from "../public-page/plugin-public-page"
import { FirstPartyPlugins } from "./first-party-plugins"
import { ThirdPartyPlugins } from "./third-party-plugins"

/** Plugins to connect: SurfSense's own first, then the registry's; each opens its public page. */
export function BrowsePlugins() {
  const [opened, setOpened] = useState<ListedEntry | null>(null)
  const fromRegistry = opened !== null && isRegistryEntry(opened)
  // The open entry as its list reads now, so the page says "Connected" once it is.
  const firstParty = useQuery({
    queryKey: firstPartyQueryKey,
    queryFn: ({ signal }) => listFirstParty(signal),
    enabled: opened !== null && !fromRegistry,
  })
  const registry = useQuery({
    queryKey: registryQueryKey,
    queryFn: ({ signal }) => listRegistry(signal),
    enabled: fromRegistry,
    retry: false,
  })
  if (opened) {
    const current = fromRegistry
      ? registry.data?.plugins.find((entry) => entry.id === opened.id)
      : firstParty.data?.find((entry) => entry.id === opened.id)
    return (
      <PluginPublicPage
        entry={current ?? opened}
        onBack={() => setOpened(null)}
      />
    )
  }
  return (
    <>
      <FirstPartyPlugins onOpen={setOpened} />
      <ThirdPartyPlugins onOpen={setOpened} />
    </>
  )
}
