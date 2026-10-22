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
import { ScrollFade } from "@/components/ui/scroll-fade"
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
import { updatePrefsQueryKey } from "@/features/updates/use-update-state"
import { intl } from "@/i18n/intl"
import type { PrivacyState } from "@/lib/api"

import { PrivacyChoiceRow } from "./privacy-choice-row"

function updatesBody(state: PrivacyState) {
  const { host, fallbackHost } = state.updates
  return fallbackHost
    ? intl.formatMessage(
        {
          id: "onboarding_privacy_updates_body",
          defaultMessage:
            "Once a day, SurfSense asks {host} whether a newer version exists, sending your IP address, the app’s name and version, your operating system and its architecture, and no ID. If {host} cannot answer, it asks github.com with only your IP address and the app’s name. A newer version downloads by itself from github.com and githubusercontent.com, which also see your IP address, and installs when you restart or the next time you quit.",
        },
        { host }
      )
    : intl.formatMessage(
        {
          id: "onboarding_privacy_updates_mirror_body",
          defaultMessage:
            "Once a day, SurfSense asks {host}, the update server your organization set, whether a newer version exists, sending your IP address, the app’s name and version, your operating system and its architecture, and no ID. A newer version downloads by itself from {host} and installs when you restart or the next time you quit.",
        },
        { host }
      )
}

/**
 * The first-run question about update checks and usage statistics: two
 * separate answers, neither chosen for the user, both needed to go on. Only a
 * new install sees it; a policy that holds one off answers it already.
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
  const usageLocked = usageLockedText(state)
  const [updates, setUpdates] = useState<boolean | null>(
    updatesLocked ? false : null
  )
  const [usage, setUsage] = useState<boolean | null>(usageLocked ? false : null)
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
          <div className="flex flex-col gap-3">
            <PrivacyChoiceRow
              title={intl.formatMessage({
                id: "onboarding_privacy_updates_title",
                defaultMessage: "Check for updates",
              })}
              body={updatesBody(state)}
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
              whatsSent={
                <WhatsSentDialog
                  topic="updates"
                  state={state}
                  label={intl.formatMessage({
                    id: "onboarding_privacy_updates_whats_sent_button",
                    defaultMessage: "See exactly what’s sent",
                  })}
                />
              }
            />
            <PrivacyChoiceRow
              title={intl.formatMessage({
                id: "onboarding_privacy_usage_title",
                defaultMessage: "Share usage statistics",
              })}
              body={intl.formatMessage(
                {
                  id: "onboarding_privacy_usage_body",
                  defaultMessage:
                    "Once a day, SurfSense tells {host} this install was used, with the app’s version, your system, the app’s language and the week it was installed. Once a week it adds counts in ranges: chats, agent turns, sources, Studio outputs, plugin calls, whether a local or remote model answered, and how far setup got. Its first report adds this computer’s memory and graphics card, in ranges. Never documents, prompts, file names, model names, hosts, your license key or an ID.",
                },
                { host: state.usageStatistics.host }
              )}
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
              whatsSent={
                <WhatsSentDialog
                  topic="usage"
                  state={state}
                  label={intl.formatMessage({
                    id: "onboarding_privacy_usage_whats_sent_button",
                    defaultMessage: "See exactly what’s sent",
                  })}
                />
              }
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
