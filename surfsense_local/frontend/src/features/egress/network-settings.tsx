import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useId } from "react"

import { RelativeTime } from "@/components/relative-time"
import { Checkbox } from "@/components/ui/checkbox"
import { DotIcon } from "@/components/ui/icons"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  updatesLockedText,
  usageLockedText,
} from "@/features/privacy-choices/locked-text"
import { usePrivacyState } from "@/features/privacy-choices/use-privacy-state"
import { SettingsSection } from "@/features/settings/settings-section"
import { useUpdatePrefs } from "@/features/updates/use-update-state"
import { intl } from "@/i18n/intl"

import {
  describeDestination,
  destinationsQueryKey,
  listDestinations,
  setDestinationsEnabled,
} from "./api"

function DestinationRow({
  label,
  host,
  enabled,
  lastCallAt,
  onChange,
  locked = null,
}: {
  label: string
  host: string
  enabled: boolean
  lastCallAt: string | null
  onChange: (enabled: boolean) => void
  /** Why a policy holds this row off, which also disables its checkbox. */
  locked?: string | null
}) {
  const checkboxId = useId()
  return (
    <li className="flex items-center justify-between gap-6 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium">{label}</p>
        {locked ? (
          <p className="text-xs text-muted-foreground">{locked}</p>
        ) : null}
        <p className="truncate text-xs text-muted-foreground">
          {host}
          <DotIcon
            aria-hidden="true"
            className="mx-1 inline size-3 align-middle"
          />
          {lastCallAt
            ? intl.formatMessage(
                {
                  id: "egress_destination_last_call_label",
                  defaultMessage: "Last call: {time}",
                },
                {
                  time: <RelativeTime date={new Date(lastCallAt)} />,
                }
              )
            : intl.formatMessage({
                id: "egress_destination_never_called_label",
                defaultMessage: "Last call: never",
              })}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2 text-sm">
        <Checkbox
          id={checkboxId}
          checked={enabled}
          disabled={locked !== null}
          onCheckedChange={(checked) => onChange(checked === true)}
        />
        <Label htmlFor={checkboxId} className="sr-only">
          {intl.formatMessage(
            {
              id: "egress_destination_allow_aria",
              defaultMessage: "Allow {name}",
            },
            { name: label }
          )}
        </Label>
      </div>
    </li>
  )
}

// Updates are an Electron pref, not an API destination.
function UpdatesRow() {
  const { prefs, setAutomatic } = useUpdatePrefs()
  const { state } = usePrivacyState()
  if (prefs === null) return null
  const updates = state?.updates
  return (
    <DestinationRow
      label={intl.formatMessage({
        id: "egress_network_app_updates_label",
        defaultMessage: "App updates",
      })}
      host={
        updates?.fallbackHost
          ? intl.formatMessage(
              {
                id: "egress_network_app_updates_host_label",
                defaultMessage: "{host}, falls back to {fallback}",
              },
              { host: updates.host, fallback: updates.fallbackHost }
            )
          : (updates?.host ?? "github.com")
      }
      enabled={prefs.automatic}
      lastCallAt={prefs.lastCheckedAt ?? null}
      locked={state ? updatesLockedText(state) : null}
      onChange={(automatic) => void setAutomatic(automatic)}
    />
  )
}

// Usage statistics are Electron main's to send, so they are its switch too.
function UsageStatisticsRow() {
  const { state, setUsageStatistics } = usePrivacyState()
  if (!state) return null
  const usage = state.usageStatistics
  return (
    <DestinationRow
      label={intl.formatMessage({
        id: "egress_network_usage_statistics_label",
        defaultMessage: "Usage statistics",
      })}
      host={usage.host}
      enabled={usage.enabled === true}
      lastCallAt={usage.lastSent?.at ?? null}
      locked={usageLockedText(state)}
      onChange={(enabled) => void setUsageStatistics(enabled)}
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
    }) => setDestinationsEnabled([destination], enabled),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: destinationsQueryKey }),
  })

  return (
    <SettingsSection
      title={intl.formatMessage({
        id: "egress_network_title",
        defaultMessage: "Network",
      })}
      description={intl.formatMessage({
        id: "egress_network_body",
        defaultMessage:
          "Everywhere SurfSense can send data. Off blocks the call outright. Nothing is enabled by default.",
      })}
    >
      {destinations.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : destinations.error ? (
        <p role="alert" className="text-sm text-destructive">
          {intl.formatMessage({
            id: "egress_network_load_error",
            defaultMessage: "Could not load network destinations.",
          })}
        </p>
      ) : (
        <ul className="divide-y">
          <UpdatesRow />
          <UsageStatisticsRow />
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
