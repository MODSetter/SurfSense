import { useQuery } from "@tanstack/react-query"
import { useId } from "react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { setDestinationEnabled } from "@/features/egress/api"
import { askEgress } from "@/features/egress/ask-egress"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import { listRegistry, registryQueryKey, type RegistryEntry } from "../api"
import { PluginIcon } from "../plugin-icon"
import { PublisherByline } from "../public-page/publisher-byline"
import { ConnectListedPlugin } from "./connect-listed-plugin"

function RegistryEntryRow({
  entry,
  onOpen,
}: {
  entry: RegistryEntry
  onOpen: () => void
}) {
  const nameId = useId()
  return (
    <li
      aria-labelledby={nameId}
      className="relative flex items-start gap-3 rounded-lg bg-secondary p-3 transition-colors hover:bg-muted"
    >
      <PluginIcon id={entry.id} name={entry.name} hasIcon={entry.has_icon} />
      <div className="min-w-0 flex-1">
        {/* Stretched over the row, so the whole entry opens its page. */}
        <button
          id={nameId}
          type="button"
          className="text-left text-sm font-medium outline-none after:absolute after:inset-0 after:rounded-lg focus-visible:after:ring-2 focus-visible:after:ring-ring"
          onClick={onOpen}
        >
          {entry.name}
        </button>
        <p className="text-xs text-muted-foreground">{entry.description}</p>
        <p className="mt-1 flex text-xs text-muted-foreground">
          <PublisherByline entry={entry} />
        </p>
        {entry.access === "external" && entry.access_note ? (
          <p className="mt-1 text-xs text-muted-foreground">
            {entry.access_note}
          </p>
        ) : null}
      </div>
      {/* Positioned, so it sits above the row's stretched button. */}
      <div className="relative">
        <ConnectListedPlugin entry={entry} />
      </div>
    </li>
  )
}

/** The refused fetch's own question, asked on the user's click rather than at load. */
function AllowRegistryHost({
  refusal,
  onAllowed,
}: {
  refusal: ApiError
  onAllowed: () => void
}) {
  const destination = String(refusal.detail.destination ?? "")
  const host = String(refusal.detail.host ?? "")
  const ask = async () => {
    const allowed = await askEgress({
      destination,
      host,
      purpose: String(refusal.detail.purpose ?? ""),
      allow: () => setDestinationEnabled(destination, true),
    })
    if (allowed) onAllowed()
  }
  return (
    <div className="flex items-center justify-between gap-6 py-3">
      <p className="text-sm text-muted-foreground">
        {intl.formatMessage(
          {
            id: "plugins_registry_host_body",
            defaultMessage:
              "SurfSense fetches the list of third-party plugins from {host}.",
          },
          { host }
        )}
      </p>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="shrink-0"
        onClick={() => void ask()}
      >
        {intl.formatMessage({
          id: "plugins_registry_host_allow_button",
          defaultMessage: "Allow",
        })}
      </Button>
    </div>
  )
}

/** Partners' and community plugins from the signed registry; nothing is fetched while third-party plugins are off. */
export function RegistryPlugins({
  allowed,
  onOpen,
}: {
  allowed: boolean
  onOpen: (entry: RegistryEntry) => void
}) {
  const registry = useQuery({
    queryKey: registryQueryKey,
    queryFn: ({ signal }) => listRegistry(signal),
    enabled: allowed,
    retry: false,
  })
  if (!allowed) return null
  const refusal =
    registry.error instanceof ApiError &&
    registry.error.code === "egress_disabled"
      ? registry.error
      : null
  const fetchedAt = registry.data?.fetched_at
  return (
    <>
      {fetchedAt ? (
        <p className="mt-1 text-xs text-muted-foreground">
          {intl.formatMessage(
            {
              id: "plugins_registry_updated_label",
              defaultMessage: "Updated {date, date, ::yyyyMMMd}",
            },
            { date: new Date(fetchedAt) }
          )}
        </p>
      ) : null}
      {registry.isLoading ? (
        <Skeleton className="mt-3 h-16 w-full" />
      ) : refusal ? (
        <AllowRegistryHost
          refusal={refusal}
          onAllowed={() => void registry.refetch()}
        />
      ) : registry.error ? (
        <p role="alert" className="py-3 text-sm text-destructive">
          {intl.formatMessage({
            id: "plugins_registry_load_error",
            defaultMessage: "Couldn’t load the list of third-party plugins.",
          })}
        </p>
      ) : registry.data?.plugins.length ? (
        <ul className="mt-3 grid gap-3 sm:grid-cols-2">
          {registry.data.plugins.map((entry) => (
            <RegistryEntryRow
              key={entry.id}
              entry={entry}
              onOpen={() => onOpen(entry)}
            />
          ))}
        </ul>
      ) : (
        <p className="py-3 text-sm text-muted-foreground">
          {intl.formatMessage({
            id: "plugins_registry_empty",
            defaultMessage: "No third-party plugins are listed yet.",
          })}
        </p>
      )}
    </>
  )
}
