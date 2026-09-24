import { Button } from "@/components/ui/button"
import { CircleAlertIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { ModelIssue } from "./model-issue"

function reason({ model, code, host }: ModelIssue): string {
  switch (code) {
    case "unreadable_secret":
      return intl.formatMessage(
        {
          id: "chat_model_issue_unreadable_key_body",
          defaultMessage:
            "Couldn’t use {model}, its saved key has to be entered again.",
        },
        { model }
      )
    case "provider_auth":
      return intl.formatMessage(
        {
          id: "chat_model_issue_key_rejected_body",
          defaultMessage: "The provider for {model} rejected its key.",
        },
        { model }
      )
    case "provider_unreachable":
      return intl.formatMessage(
        {
          id: "chat_model_issue_unreachable_body",
          defaultMessage: "Couldn’t reach the server for {model}.",
        },
        { model }
      )
    case "egress_disabled":
      return intl.formatMessage(
        {
          id: "chat_model_issue_egress_off_body",
          defaultMessage: "Sending data to {host} is off.",
        },
        { host: host ?? model }
      )
    case "provider_rate_limited":
      return intl.formatMessage(
        {
          id: "chat_model_issue_rate_limited_body",
          defaultMessage:
            "The provider for {model} is limiting requests. Try again in a moment.",
        },
        { model }
      )
    default:
      return intl.formatMessage(
        {
          id: "chat_model_issue_unknown_body",
          defaultMessage: "Couldn’t use {model} right now.",
        },
        { model }
      )
  }
}

// Stays beside the composer until it is answered: a toast would be gone
// before the user reached "Set up model", taking the reason with it. Allow
// opens the egress consent dialog, so the question is only ever put on request.
export function ModelIssueNotice({
  issue,
  onAllow,
  onOpenSettings,
}: {
  issue: ModelIssue
  onAllow?: () => void
  onOpenSettings: () => void
}) {
  return (
    <div
      role="status"
      className="flex items-center gap-2 rounded-t-2xl border border-b-0 bg-muted px-3 pt-1 pb-5 text-xs text-muted-foreground"
    >
      <CircleAlertIcon className="size-4 shrink-0 text-destructive" />
      <p className="min-w-0 flex-1 text-pretty">{reason(issue)}</p>
      {onAllow ? (
        <Button
          type="button"
          size="xs"
          className="h-5 shrink-0"
          onClick={onAllow}
        >
          {intl.formatMessage({
            id: "chat_model_issue_allow_button",
            defaultMessage: "Allow…",
          })}
        </Button>
      ) : null}
      <Button
        type="button"
        variant="outline"
        size="xs"
        className="h-5 shrink-0"
        onClick={onOpenSettings}
      >
        {intl.formatMessage({
          id: "chat_model_issue_settings_button",
          defaultMessage: "Open settings",
        })}
      </Button>
    </div>
  )
}
