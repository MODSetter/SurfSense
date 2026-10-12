import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useId } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import {
  connectFirstParty,
  firstPartyQueryKey,
  listFirstParty,
  pluginsQueryKey,
  type FirstPartyEntry,
} from "./api"
import { refusalMessage } from "./refusal-message"

function FirstPartyEntryRow({ entry }: { entry: FirstPartyEntry }) {
  const queryClient = useQueryClient()
  const connect = useMutation({
    mutationFn: () => connectFirstParty(entry.id),
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: pluginsQueryKey }),
        queryClient.invalidateQueries({ queryKey: firstPartyQueryKey }),
      ]),
  })
  return (
    <li className="flex items-start justify-between gap-6 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium">{entry.name}</p>
        <p className="text-xs text-muted-foreground">{entry.description}</p>
        {entry.access === "license" ? (
          <p className="mt-1 text-xs text-muted-foreground">
            {intl.formatMessage({
              id: "plugins_first_party_license_label",
              defaultMessage: "License required",
            })}
          </p>
        ) : null}
        {connect.error ? (
          <p role="alert" className="mt-1 text-xs text-destructive">
            {refusalMessage(connect.error)}
          </p>
        ) : null}
      </div>
      {entry.connected ? (
        <span className="shrink-0 text-xs text-muted-foreground">
          {intl.formatMessage({
            id: "plugins_first_party_connected_status",
            defaultMessage: "Connected",
          })}
        </span>
      ) : (
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="shrink-0"
          disabled={connect.isPending}
          onClick={() => connect.mutate()}
        >
          {connect.isPending ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "plugins_first_party_connect_button",
            defaultMessage: "Connect",
          })}
        </Button>
      )}
    </li>
  )
}

/** SurfSense's own plugins, listed from the app with no network or consent until Connect. */
export function FirstPartyPlugins() {
  const titleId = useId()
  const entries = useQuery({
    queryKey: firstPartyQueryKey,
    queryFn: ({ signal }) => listFirstParty(signal),
  })
  if (!entries.data?.length) return null
  return (
    <section aria-labelledby={titleId} className="mb-8">
      <h3 id={titleId} className="text-sm font-medium">
        {intl.formatMessage({
          id: "plugins_first_party_title",
          defaultMessage: "By SurfSense",
        })}
      </h3>
      <ul className="divide-y">
        {entries.data.map((entry) => (
          <FirstPartyEntryRow key={entry.id} entry={entry} />
        ))}
      </ul>
    </section>
  )
}
