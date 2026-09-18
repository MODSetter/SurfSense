import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useId } from "react"

import { RelativeTime } from "@/components/relative-time"
import { Checkbox } from "@/components/ui/checkbox"
import { DotIcon } from "@/components/ui/icons"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { SettingsSection } from "@/features/settings/settings-section"
import { useUpdatePrefs } from "@/features/updates/use-update-state"

import {
  describeDestination,
  destinationsQueryKey,
  listDestinations,
  setDestinationEnabled,
} from "./api"

function DestinationRow({
  label,
  host,
  enabled,
  lastCallAt,
  onChange,
}: {
  label: string
  host: string
  enabled: boolean
  lastCallAt: string | null
  onChange: (enabled: boolean) => void
}) {
  const checkboxId = useId()
  return (
    <li className="flex items-center justify-between gap-6 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium">{label}</p>
        <p className="truncate text-xs text-muted-foreground">
          {host}
          <DotIcon
            aria-hidden="true"
            className="mx-1 inline size-3 align-middle"
          />
          Last call:{" "}
          {lastCallAt ? <RelativeTime date={new Date(lastCallAt)} /> : "never"}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2 text-sm">
        <Checkbox
          id={checkboxId}
          checked={enabled}
          onCheckedChange={(checked) => onChange(checked === true)}
        />
        <Label htmlFor={checkboxId} className="sr-only">
          Allow {label}
        </Label>
      </div>
    </li>
  )
}

// Updates are an Electron pref, not an API destination.
function UpdatesRow() {
  const { prefs, setAutomatic } = useUpdatePrefs()
  if (prefs === null) return null
  return (
    <DestinationRow
      label="App updates"
      host="github.com"
      enabled={prefs.automatic}
      lastCallAt={prefs.lastCheckedAt ?? null}
      onChange={(automatic) => void setAutomatic(automatic)}
    />
  )
}

export function NetworkSettings() {
  const queryClient = useQueryClient()
  const destinations = useQuery({
    queryKey: destinationsQueryKey,
    queryFn: ({ signal }) => listDestinations(signal),
  })
  const toggle = useMutation({
    mutationFn: ({
      destination,
      enabled,
    }: {
      destination: string
      enabled: boolean
    }) => setDestinationEnabled(destination, enabled),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: destinationsQueryKey }),
  })

  return (
    <SettingsSection
      title="Network"
      description="Everywhere SurfSense can send data. Off blocks the call outright. Nothing is enabled by default."
    >
      {destinations.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : destinations.error ? (
        <p role="alert" className="text-sm text-destructive">
          Could not load network destinations.
        </p>
      ) : (
        <ul className="divide-y">
          <UpdatesRow />
          {destinations.data?.map((row) => (
            <DestinationRow
              key={row.destination}
              label={describeDestination(row.destination, row.host).label}
              host={row.host}
              enabled={row.enabled}
              lastCallAt={row.last_call_at}
              onChange={(enabled) =>
                toggle.mutate({ destination: row.destination, enabled })
              }
            />
          ))}
        </ul>
      )}
    </SettingsSection>
  )
}
