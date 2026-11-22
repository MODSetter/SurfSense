import { useQuery, type UseQueryResult } from "@tanstack/react-query"
import { useId, useState, type ReactNode } from "react"

import { useDebouncedValue } from "@/hooks/use-debounced-value"
import { intl } from "@/i18n/intl"

import {
  firstPartyQueryKey,
  listFirstParty,
  listRegistry,
  registryQueryKey,
  thirdPartyAllowed,
  thirdPartyQueryKey,
  type Plugin,
} from "../api"
import { FirstPartyEntryRow } from "../browse/first-party-plugins"
import { RegistryEntryRow } from "../browse/registry-plugins"
import { PluginDetails } from "../details/plugin-details"
import { isRegistryEntry, type ListedEntry } from "../public-page/listed-entry"
import { PluginPublicPage } from "../public-page/plugin-public-page"
import { ConnectedPluginsTable } from "../yours/connected-plugins-table"
import { connectedFields, listedFields, matchesQuery } from "./plugin-matches"
import { SearchResultsSkeleton } from "./search-results-skeleton"

// The lists are already in memory, so this only lets a burst of keystrokes settle.
const SETTLE_MS = 200

/** What a result opened, for the query it was opened from; typing again closes it. */
type Opened =
  { query: string; connectedId: string } | { query: string; entry: ListedEntry }

function ResultSection({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  const titleId = useId()
  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-3">
      <h3 id={titleId} className="text-sm font-medium">
        {title}
      </h3>
      {children}
    </section>
  )
}

/** Connected plugins first, then the listed ones not yet connected, from both lists. */
export function PluginSearchResults({
  query,
  plugins,
  onOpenLicense,
}: {
  query: string
  plugins: UseQueryResult<Plugin[]>
  onOpenLicense?: () => void
}) {
  const wanted = query.trim()
  const settled = useDebouncedValue(wanted, SETTLE_MS)
  const [opened, setOpened] = useState<Opened | null>(null)
  const thirdParty = useQuery({
    queryKey: thirdPartyQueryKey,
    queryFn: ({ signal }) => thirdPartyAllowed(signal),
  })
  const allowed = thirdParty.data ?? false
  const firstParty = useQuery({
    queryKey: firstPartyQueryKey,
    queryFn: ({ signal }) => listFirstParty(signal),
  })
  // Fetched only once third-party plugins are allowed, as Browse does.
  const registry = useQuery({
    queryKey: registryQueryKey,
    queryFn: ({ signal }) => listRegistry(signal),
    enabled: allowed,
    retry: false,
  })

  const open = opened?.query === wanted ? opened : null
  if (open && "connectedId" in open) {
    const plugin = plugins.data?.find((row) => row.id === open.connectedId)
    if (plugin) {
      return (
        <PluginDetails
          plugin={plugin}
          thirdPartyAllowed={allowed}
          onBack={() => setOpened(null)}
          onOpenLicense={onOpenLicense}
        />
      )
    }
  } else if (open) {
    // The entry as its list reads now, so the page says "Connected" once it is.
    const current = isRegistryEntry(open.entry)
      ? registry.data?.plugins.find((entry) => entry.id === open.entry.id)
      : firstParty.data?.find((entry) => entry.id === open.entry.id)
    return (
      <PluginPublicPage
        entry={current ?? open.entry}
        onBack={() => setOpened(null)}
      />
    )
  }

  const pending =
    settled !== wanted ||
    plugins.isLoading ||
    thirdParty.isLoading ||
    firstParty.isLoading ||
    (allowed && registry.isLoading)
  const matches = (fields: (string | null | undefined)[]) =>
    matchesQuery(settled, fields)
  const yours = (plugins.data ?? []).filter((plugin) =>
    matches(connectedFields(plugin))
  )
  const ownToAdd = (firstParty.data ?? []).filter(
    (entry) => !entry.connected && matches(listedFields(entry))
  )
  const thirdPartyToAdd = allowed
    ? (registry.data?.plugins ?? []).filter(
        (entry) => !entry.connected && matches(listedFields(entry))
      )
    : []
  const none = !yours.length && !ownToAdd.length && !thirdPartyToAdd.length

  return (
    <section
      aria-label={intl.formatMessage({
        id: "plugins_search_results_aria",
        defaultMessage: "Search results",
      })}
      aria-busy={pending}
      className="flex flex-col gap-8"
    >
      {pending ? (
        <SearchResultsSkeleton />
      ) : none ? (
        <p className="text-sm text-muted-foreground">
          {intl.formatMessage(
            {
              id: "plugins_search_empty",
              defaultMessage: "No plugins match “{query}”.",
            },
            { query: settled }
          )}
        </p>
      ) : (
        <>
          {yours.length ? (
            <ResultSection
              title={intl.formatMessage({
                id: "plugins_search_yours_title",
                defaultMessage: "Yours",
              })}
            >
              <ConnectedPluginsTable
                plugins={yours}
                thirdPartyAllowed={allowed}
                onOpen={(id) => setOpened({ query: wanted, connectedId: id })}
              />
            </ResultSection>
          ) : null}
          {ownToAdd.length || thirdPartyToAdd.length ? (
            <ResultSection
              title={intl.formatMessage({
                id: "plugins_search_available_title",
                defaultMessage: "Available",
              })}
            >
              <ul className="flex flex-col">
                {ownToAdd.map((entry) => (
                  <FirstPartyEntryRow
                    key={entry.id}
                    entry={entry}
                    layout="row"
                    onOpen={() => setOpened({ query: wanted, entry })}
                  />
                ))}
                {thirdPartyToAdd.map((entry) => (
                  <RegistryEntryRow
                    key={entry.id}
                    entry={entry}
                    layout="row"
                    onOpen={() => setOpened({ query: wanted, entry })}
                  />
                ))}
              </ul>
            </ResultSection>
          ) : null}
        </>
      )}
      {!pending && !allowed ? (
        <p className="text-xs text-muted-foreground">
          {intl.formatMessage({
            id: "plugins_search_third_party_off_body",
            defaultMessage:
              "Third-party plugins aren’t searched until you allow them in Browse.",
          })}
        </p>
      ) : null}
    </section>
  )
}
