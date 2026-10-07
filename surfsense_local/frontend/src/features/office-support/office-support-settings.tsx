import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { setDestinationEnabled } from "@/features/egress/api"
import { SettingsSection } from "@/features/settings/settings-section"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import {
  confirmInstalledOffice,
  installOffice,
  officeQueryKey,
  removeOffice,
  type OfficeStatus,
} from "./api"
import { OfficeConsentDialog } from "./office-consent-dialog"
import { errorMessage, refusalMessage } from "./office-messages"
import { useOfficeStatus } from "./use-office-status"

const BUSY = new Set(["downloading", "unpacking", "checking"])
const ON = new Set(["installed", "using_installed"])

function phaseLabel(state: OfficeStatus["state"]): string {
  if (state === "unpacking") {
    return intl.formatMessage({
      id: "office_support_phase_unpacking_status",
      defaultMessage: "Unpacking LibreOffice…",
    })
  }
  if (state === "checking") {
    return intl.formatMessage({
      id: "office_support_phase_checking_status",
      defaultMessage: "Checking that LibreOffice runs…",
    })
  }
  return intl.formatMessage({
    id: "office_support_phase_downloading_status",
    defaultMessage: "Downloading LibreOffice…",
  })
}

/** A refused call's sentence, from its code; `describe` reads that call's codes. */
function failureOf(error: unknown, describe: (code: string) => string): string {
  if (error instanceof ApiError && error.code) return describe(error.code)
  if (error instanceof ApiError) return error.message
  return describe("")
}

/** `askConsent` opens the download's consent at once, as a thread's offer asks. */
export function OfficeSupportSettings({
  askConsent = false,
}: {
  askConsent?: boolean
}) {
  const client = useQueryClient()
  const status = useOfficeStatus()
  const [consenting, setConsenting] = useState(askConsent)
  const receive = (next: OfficeStatus) =>
    client.setQueryData(officeQueryKey, next)

  const install = useMutation({
    mutationFn: async (destination: string) => {
      // The dialog named this host and what is sent, so it is the host's consent.
      await setDestinationEnabled(destination, true)
      return installOffice()
    },
    onSuccess: receive,
  })
  const useMine = useMutation({
    mutationFn: confirmInstalledOffice,
    onSuccess: receive,
  })
  const remove = useMutation({ mutationFn: removeOffice, onSuccess: receive })
  const failed = useMine.error
    ? failureOf(useMine.error, refusalMessage)
    : (install.error ?? remove.error)
      ? failureOf(install.error ?? remove.error, errorMessage)
      : null

  const office = status.data
  return (
    <SettingsSection
      title={intl.formatMessage({
        id: "office_support_settings_title",
        defaultMessage: "Office support",
      })}
      description={intl.formatMessage({
        id: "office_support_settings_body",
        defaultMessage:
          "LibreOffice lets SurfSense show Word and PowerPoint pages as Office lays them out, put real totals in the workbooks it makes, and convert documents to PDF. It is optional, free, and nothing downloads until you turn it on.",
      })}
    >
      {status.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : !office ? (
        <p role="alert" className="text-sm text-destructive">
          {intl.formatMessage({
            id: "office_support_settings_load_error",
            defaultMessage: "Could not load Office support.",
          })}
        </p>
      ) : (
        <div className="flex flex-col gap-6">
          <OfficeState
            office={office}
            onTurnOn={() => setConsenting(true)}
            onRemove={() => remove.mutate()}
            removing={remove.isPending}
          />
          <DetectedOffice
            office={office}
            onUse={() => useMine.mutate()}
            using={useMine.isPending}
          />
          {failed ? (
            <p role="alert" className="text-sm text-destructive">
              {failed}
            </p>
          ) : null}
          <p className="text-xs text-pretty text-muted-foreground">
            {intl.formatMessage({
              id: "office_support_settings_licence_body",
              defaultMessage:
                "LibreOffice is made by The Document Foundation and is free software under the Mozilla Public License 2.0. SurfSense runs it with its own settings: macros, links to other files and LibreOffice’s own updates are off.",
            })}
          </p>
          {office.offer ? (
            <OfficeConsentDialog
              offer={office.offer}
              open={
                consenting && !BUSY.has(office.state) && !ON.has(office.state)
              }
              onOpenChange={setConsenting}
              onDownload={() => {
                if (office.offer) install.mutate(office.offer.destination)
              }}
            />
          ) : null}
        </div>
      )}
    </SettingsSection>
  )
}

function OfficeState({
  office,
  onTurnOn,
  onRemove,
  removing,
}: {
  office: OfficeStatus
  onTurnOn: () => void
  onRemove: () => void
  removing: boolean
}) {
  if (BUSY.has(office.state)) {
    const progress = office.progress
    const percent =
      progress && progress.total > 0
        ? Math.round((progress.completed / progress.total) * 100)
        : null
    return (
      <div className="flex items-center gap-6">
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <p className="text-sm font-medium">{phaseLabel(office.state)}</p>
          <Progress
            value={percent}
            aria-label={phaseLabel(office.state)}
            className="w-full"
          />
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={onRemove}
          disabled={removing}
        >
          {intl.formatMessage({
            id: "office_support_settings_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
      </div>
    )
  }
  if (ON.has(office.state)) {
    return (
      <div className="flex items-center justify-between gap-8">
        <div className="flex min-w-0 flex-col gap-1">
          <h3 className="text-sm font-medium">
            {intl.formatMessage(
              {
                id: "office_support_settings_on_status",
                defaultMessage: "On: LibreOffice {version}",
              },
              { version: office.version ?? "" }
            )}
          </h3>
          {office.state === "using_installed" && office.path ? (
            <p className="truncate text-sm text-muted-foreground">
              {intl.formatMessage(
                {
                  id: "office_support_settings_using_yours_status",
                  defaultMessage: "Your own install at {path}",
                },
                { path: office.path }
              )}
            </p>
          ) : null}
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={onRemove}
          disabled={removing}
        >
          {office.state === "installed"
            ? intl.formatMessage({
                id: "office_support_settings_remove_button",
                defaultMessage: "Remove",
              })
            : intl.formatMessage({
                id: "office_support_settings_stop_using_button",
                defaultMessage: "Stop using it",
              })}
        </Button>
      </div>
    )
  }
  return (
    <div className="flex items-center justify-between gap-8">
      <div className="flex min-w-0 flex-col gap-1">
        <h3 className="text-sm font-medium">
          {intl.formatMessage({
            id: "office_support_settings_off_status",
            defaultMessage: "Off",
          })}
        </h3>
        {office.state === "error" && office.error ? (
          <p role="alert" className="text-sm text-pretty text-destructive">
            {errorMessage(office.error.code)}
          </p>
        ) : null}
        {!office.offer ? (
          <p className="text-sm text-pretty text-muted-foreground">
            {intl.formatMessage({
              id: "office_support_settings_no_download_body",
              defaultMessage:
                "No LibreOffice download is offered for this computer yet. You can use one you install yourself.",
            })}
          </p>
        ) : null}
      </div>
      {office.offer ? (
        <Button type="button" onClick={onTurnOn}>
          {intl.formatMessage({
            id: "office_support_settings_turn_on_button",
            defaultMessage: "Turn on",
          })}
        </Button>
      ) : null}
    </div>
  )
}

function DetectedOffice({
  office,
  onUse,
  using,
}: {
  office: OfficeStatus
  onUse: () => void
  using: boolean
}) {
  const found = office.detected
  // Once Office support is on, the pack or the confirmed install is what runs.
  if (!found || ON.has(office.state) || BUSY.has(office.state)) return null
  return (
    <div className="flex items-center justify-between gap-8 border-t pt-6">
      <div className="flex min-w-0 flex-col gap-1">
        <h3 className="text-sm font-medium">
          {found.branch
            ? intl.formatMessage(
                {
                  id: "office_support_detected_title",
                  defaultMessage: "LibreOffice {branch} is installed",
                },
                { branch: found.branch }
              )
            : intl.formatMessage({
                id: "office_support_detected_unknown_title",
                defaultMessage: "LibreOffice is installed",
              })}
        </h3>
        <p className="truncate text-sm text-muted-foreground">{found.path}</p>
        {found.usable ? null : (
          <p className="text-sm text-pretty text-muted-foreground">
            {refusalMessage(found.refusal)}
          </p>
        )}
      </div>
      {found.usable ? (
        <Button
          type="button"
          variant="outline"
          onClick={onUse}
          disabled={using}
        >
          {intl.formatMessage({
            id: "office_support_detected_use_button",
            defaultMessage: "Use the LibreOffice I have",
          })}
        </Button>
      ) : null}
    </div>
  )
}
