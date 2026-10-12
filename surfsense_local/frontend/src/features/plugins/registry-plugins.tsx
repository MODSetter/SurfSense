import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useId, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CheckIcon } from "@/components/ui/icons"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { setDestinationEnabled } from "@/features/egress/api"
import { askEgress } from "@/features/egress/ask-egress"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import {
  connectRegistryPlugin,
  isSignInStarted,
  listRegistry,
  pluginsQueryKey,
  registryQueryKey,
  type RegistryEntry,
} from "./api"
import { PluginIcon } from "./plugin-icon"
import { refusalMessage } from "./refusal-message"
import { RegistryKeyDialog } from "./registry-key-dialog"
import { SignInProgress } from "./sign-in-progress"
import { usePluginSignIn } from "./use-plugin-sign-in"

function Attribution({ entry }: { entry: RegistryEntry }) {
  if (entry.verified) {
    return (
      <span className="flex items-center gap-1.5">
        <span className="truncate">{entry.author}</span>
        <Badge variant="secondary">
          <CheckIcon data-icon="inline-start" />
          {intl.formatMessage({
            id: "plugins_registry_verified_label",
            defaultMessage: "Verified",
          })}
        </Badge>
      </span>
    )
  }
  return (
    <span className="truncate">
      {intl.formatMessage(
        { id: "plugins_registry_author_label", defaultMessage: "By {author}" },
        { author: entry.author }
      )}
    </span>
  )
}

function RegistryEntryRow({ entry }: { entry: RegistryEntry }) {
  const nameId = useId()
  const queryClient = useQueryClient()
  const [askingKey, setAskingKey] = useState(false)
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: pluginsQueryKey }),
      queryClient.invalidateQueries({ queryKey: registryQueryKey }),
    ])
  const signIn = usePluginSignIn(() => void refresh())
  const connect = useMutation({
    mutationFn: () => connectRegistryPlugin(entry.id),
    onSuccess: (answer) => {
      // An account's sign-in finishes in the browser; the plugin exists only then.
      if (isSignInStarted(answer)) signIn.follow(answer)
      else void refresh()
    },
    onError: () => void refresh(),
  })
  const waiting = signIn.state.phase === "waiting"
  return (
    <li aria-labelledby={nameId} className="flex items-start gap-3 py-3">
      <PluginIcon id={entry.id} name={entry.name} hasIcon={entry.has_icon} />
      <div className="min-w-0 flex-1">
        <p id={nameId} className="text-sm font-medium">
          {entry.name}
        </p>
        <p className="text-xs text-muted-foreground">{entry.description}</p>
        <p className="mt-1 flex text-xs text-muted-foreground">
          <Attribution entry={entry} />
        </p>
        {entry.access === "external" && entry.access_note ? (
          <p className="mt-1 text-xs text-muted-foreground">
            {entry.access_note}
          </p>
        ) : null}
        <SignInProgress state={signIn.state} onCancel={signIn.cancel} />
        {connect.error ? (
          <p role="alert" className="mt-1 text-xs text-destructive">
            {refusalMessage(connect.error)}
          </p>
        ) : null}
      </div>
      {entry.connected ? (
        <span className="shrink-0 text-xs text-muted-foreground">
          {intl.formatMessage({
            id: "plugins_registry_connected_status",
            defaultMessage: "Connected",
          })}
        </span>
      ) : (
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="shrink-0"
          disabled={waiting || connect.isPending}
          onClick={() =>
            entry.auth_type === "token" ? setAskingKey(true) : connect.mutate()
          }
        >
          {connect.isPending ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "plugins_registry_connect_button",
            defaultMessage: "Connect",
          })}
        </Button>
      )}
      {entry.auth_type === "token" ? (
        <RegistryKeyDialog
          entry={entry}
          open={askingKey}
          onOpenChange={setAskingKey}
          onConnected={() => {
            setAskingKey(false)
            void refresh()
          }}
        />
      ) : null}
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
export function RegistryPlugins({ allowed }: { allowed: boolean }) {
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
        <ul className="divide-y">
          {registry.data.plugins.map((entry) => (
            <RegistryEntryRow key={entry.id} entry={entry} />
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
