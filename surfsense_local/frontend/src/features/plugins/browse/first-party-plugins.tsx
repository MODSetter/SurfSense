import { useQuery } from "@tanstack/react-query"
import { useId } from "react"

import { intl } from "@/i18n/intl"

import {
  firstPartyQueryKey,
  listFirstParty,
  type FirstPartyEntry,
} from "../api"
import { PluginIcon } from "../plugin-icon"
import { ConnectListedPlugin } from "./connect-listed-plugin"

function FirstPartyEntryRow({
  entry,
  onOpen,
}: {
  entry: FirstPartyEntry
  onOpen: () => void
}) {
  const nameId = useId()
  return (
    <li
      aria-labelledby={nameId}
      className="relative flex items-start gap-3 py-3"
    >
      <PluginIcon
        id={entry.id}
        name={entry.name}
        hasIcon={entry.has_icon}
        firstParty
      />
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
        {entry.access === "license" ? (
          <p className="mt-1 text-xs text-muted-foreground">
            {intl.formatMessage({
              id: "plugins_first_party_license_label",
              defaultMessage: "License required",
            })}
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

/** SurfSense's own plugins, listed from the app with no network or consent until Connect. */
export function FirstPartyPlugins({
  onOpen,
}: {
  onOpen: (entry: FirstPartyEntry) => void
}) {
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
      <ul className="grid gap-x-8 sm:grid-cols-2">
        {entries.data.map((entry) => (
          <FirstPartyEntryRow
            key={entry.id}
            entry={entry}
            onOpen={() => onOpen(entry)}
          />
        ))}
      </ul>
    </section>
  )
}
