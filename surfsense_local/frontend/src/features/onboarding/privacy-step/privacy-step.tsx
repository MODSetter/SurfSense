import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ChartHistogramIcon, RefreshCwIcon } from "@/components/ui/icons"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import {
  updatesLockedText,
  usageLockedText,
} from "@/features/privacy-choices/locked-text"
import {
  privacyBridge,
  privacyStateQueryKey,
} from "@/features/privacy-choices/use-privacy-state"
import { WhatsSentDialog } from "@/features/privacy-choices/whats-sent-dialog"
import { updatesText, usageText } from "@/features/privacy-choices/choice-text"
import { updatePrefsQueryKey } from "@/features/updates/use-update-state"
import { intl } from "@/i18n/intl"
import type { PrivacyState } from "@/lib/api"

import { PrivacyChoiceRow } from "./privacy-choice-row"

/**
 * Onboarding's first step, about update checks and usage statistics: two
 * separate answers, both needed to go on. A new install has neither chosen for
 * it; one that answered before sees its answers. A policy or package manager
 * that holds one off answers it already.
 */
export function PrivacyStep({
  state,
  onDone,
}: {
  state: PrivacyState
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const updatesLocked = updatesLockedText(state)
  // A package manager owns updates, so no check is described, as in Settings.
  const channelLocked = state.updates.lockedReason === "channel"
  const usageLocked = usageLockedText(state)
  const [updates, setUpdates] = useState<boolean | null>(
    updatesLocked ? false : state.firstRunAsked ? state.updates.automatic : null
  )
  const [usage, setUsage] = useState<boolean | null>(
    usageLocked
      ? false
      : state.firstRunAsked
        ? (state.usageStatistics.enabled ?? null)
        : null
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const answered = updates !== null && usage !== null

  const save = async () => {
    const privacy = privacyBridge()
    if (!privacy || updates === null || usage === null) return
    setSaving(true)
    setError(null)
    try {
      await privacy.completeFirstRun({ updates, usageStatistics: usage })
      void queryClient.invalidateQueries({ queryKey: privacyStateQueryKey })
      void queryClient.invalidateQueries({ queryKey: updatePrefsQueryKey })
      onDone()
    } catch {
      setError(
        intl.formatMessage({
          id: "onboarding_privacy_save_error",
          defaultMessage: "Could not save your choices. Try again.",
        })
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="max-h-full min-h-0 w-full gap-0 [--card-spacing:--spacing(6)]">
      <CardHeader className="mb-(--card-spacing)">
        <CardTitle>
          <h1 className="font-heading text-xl text-balance">
            {intl.formatMessage({
              id: "onboarding_privacy_title",
              defaultMessage: "Privacy choices",
            })}
          </h1>
        </CardTitle>
        <CardDescription className="max-w-lg text-pretty">
          {intl.formatMessage({
            id: "onboarding_privacy_body",
            defaultMessage:
              "Choose whether SurfSense may do each of these. Nothing is sent until you choose, and you can change both later in Settings.",
          })}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col gap-3 px-0">
        <ScrollFade
          className="min-h-0 flex-1"
          viewportClassName="px-(--card-spacing) pb-1"
        >
          <div className="flex flex-col">
            <PrivacyChoiceRow
              icon={RefreshCwIcon}
              title={intl.formatMessage({
                id: "onboarding_privacy_updates_title",
                defaultMessage: "Check for updates",
              })}
              text={channelLocked ? undefined : updatesText(state)}
              whatsSent={
                channelLocked ? undefined : (
                  <WhatsSentDialog
                    topic="updates"
                    state={state}
                    label={intl.formatMessage({
                      id: "onboarding_privacy_updates_whats_sent_button",
                      defaultMessage: "Show exactly what’s sent",
                    })}
                  />
                )
              }
              locked={updatesLocked}
              value={updates}
              onChange={setUpdates}
              yesLabel={intl.formatMessage({
                id: "onboarding_privacy_updates_yes_button",
                defaultMessage: "Yes",
              })}
              noLabel={intl.formatMessage({
                id: "onboarding_privacy_updates_no_button",
                defaultMessage: "No",
              })}
            />
            <Separator />
            <PrivacyChoiceRow
              icon={ChartHistogramIcon}
              title={intl.formatMessage({
                id: "onboarding_privacy_usage_title",
                defaultMessage: "Share usage statistics",
              })}
              text={usageText(state)}
              whatsSent={
                <WhatsSentDialog
                  topic="usage"
                  state={state}
                  label={intl.formatMessage({
                    id: "onboarding_privacy_usage_whats_sent_button",
                    defaultMessage: "Show exactly what’s sent",
                  })}
                />
              }
              locked={usageLocked}
              value={usage}
              onChange={setUsage}
              yesLabel={intl.formatMessage({
                id: "onboarding_privacy_usage_yes_button",
                defaultMessage: "Yes",
              })}
              noLabel={intl.formatMessage({
                id: "onboarding_privacy_usage_no_button",
                defaultMessage: "No",
              })}
            />
          </div>
        </ScrollFade>
        {error ? (
          <p
            className="px-(--card-spacing) text-sm text-destructive"
            aria-live="polite"
          >
            {error}
          </p>
        ) : null}
      </CardContent>

      <CardFooter className="justify-end gap-3 border-t py-4">
        {answered ? null : (
          <p className="text-sm text-muted-foreground">
            {intl.formatMessage({
              id: "onboarding_privacy_unanswered_status",
              defaultMessage: "Answer both to continue.",
            })}
          </p>
        )}
        <Button
          type="button"
          disabled={!answered || saving}
          onClick={() => void save()}
        >
          {saving ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "onboarding_privacy_continue_button",
            defaultMessage: "Continue",
          })}
        </Button>
      </CardFooter>
    </Card>
  )
}
