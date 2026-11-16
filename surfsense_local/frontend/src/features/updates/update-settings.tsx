import { Button } from "@/components/ui/button"
import { updatesText } from "@/features/privacy-choices/choice-text"
import { DetailsTooltip } from "@/features/privacy-choices/details-tooltip"
import { updatesLockedText } from "@/features/privacy-choices/locked-text"
import { usePrivacyState } from "@/features/privacy-choices/use-privacy-state"
import { WhatsSentDialog } from "@/features/privacy-choices/whats-sent-dialog"
import { intl } from "@/i18n/intl"
import type { UpdateState } from "@/lib/api"

import { useCheckForUpdates } from "./use-check-for-updates"
import {
  updatesBridge,
  useUpdatePrefs,
  useUpdateState,
} from "./use-update-state"

export type { UpdateState }

function statusText(state: UpdateState) {
  switch (state.status) {
    case "checking":
      return intl.formatMessage({
        id: "updates_settings_checking_status",
        defaultMessage: "Checking…",
      })
    case "up-to-date":
      return intl.formatMessage({
        id: "updates_settings_up_to_date_status",
        defaultMessage: "SurfSense is up to date",
      })
    case "downloading":
      return intl.formatMessage(
        {
          id: "updates_settings_downloading_status",
          defaultMessage: "Downloading {version}…",
        },
        {
          version: state.version,
        }
      )
    case "ready":
      return intl.formatMessage(
        {
          id: "updates_settings_ready_status",
          defaultMessage:
            "SurfSense {version} is ready. It installs when you restart or the next time you quit.",
        },
        { version: state.version }
      )
    default:
      return null
  }
}

export function UpdateSettings() {
  const updates = updatesBridge()
  const state = useUpdateState()
  const { prefs } = useUpdatePrefs()
  const onCheckClick = useCheckForUpdates()
  const { state: privacy } = usePrivacyState()

  if (!updates || prefs === null) return null

  const text = statusText(state)
  const locked = privacy ? updatesLockedText(privacy) : null
  // A package manager's install never asks the feed, so there is no daily
  // check to describe and no request to show.
  const channelLocked = privacy?.updates.lockedReason === "channel"
  const described = privacy && !channelLocked ? updatesText(privacy) : null
  return (
    <div className="mt-8 flex items-start justify-between gap-8">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-1.5">
          <h3 className="text-sm font-medium">
            {intl.formatMessage({
              id: "updates_settings_title",
              defaultMessage: "App updates",
            })}
          </h3>
          {described ? (
            <DetailsTooltip
              label={described.label}
              details={described.details}
            />
          ) : null}
        </div>
        {described ? (
          <p className="text-sm text-pretty text-muted-foreground">
            {described.summary}
          </p>
        ) : privacy === null ? (
          // No privacy bridge: an Electron main that still reads GitHub's releases.
          <p className="text-sm text-pretty text-muted-foreground">
            {intl.formatMessage({
              id: "updates_settings_github_body",
              defaultMessage:
                "Free updates from GitHub. Once you allow update checks, SurfSense also checks each time it starts.",
            })}
          </p>
        ) : null}
        {locked ? (
          <p className="text-sm text-muted-foreground">{locked}</p>
        ) : null}
        {state.status === "error" ? (
          <p role="alert" className="text-sm text-destructive">
            {intl.formatMessage(
              {
                id: "updates_settings_check_error",
                defaultMessage: "Could not check for updates: {message}",
              },
              { message: state.message }
            )}
          </p>
        ) : text ? (
          <p className="text-sm text-muted-foreground">{text}</p>
        ) : null}
        {privacy && !channelLocked ? (
          <WhatsSentDialog
            topic="updates"
            state={privacy}
            label={intl.formatMessage({
              id: "updates_settings_whats_sent_button",
              defaultMessage: "Show exactly what’s sent",
            })}
          />
        ) : null}
      </div>
      {state.status === "ready" ? (
        <Button type="button" onClick={() => void updates.install()}>
          {intl.formatMessage({
            id: "updates_settings_restart_button",
            defaultMessage: "Restart to update",
          })}
        </Button>
      ) : (
        <Button
          type="button"
          variant="outline"
          disabled={
            locked !== null ||
            state.status === "checking" ||
            state.status === "downloading"
          }
          onClick={() => void onCheckClick()}
        >
          {intl.formatMessage({
            id: "updates_settings_check_button",
            defaultMessage: "Check now",
          })}
        </Button>
      )}
    </div>
  )
}
