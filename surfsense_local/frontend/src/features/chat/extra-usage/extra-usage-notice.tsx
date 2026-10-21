import { CircleAlertIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { ExtraUsage } from "./extra-usage-store"

function said({ resetsAt }: ExtraUsage): string {
  return resetsAt === null
    ? intl.formatMessage({
        id: "chat_composer_extra_usage_body",
        defaultMessage:
          "Your plan’s limit is reached, so replies use extra usage.",
      })
    : intl.formatMessage(
        {
          id: "chat_composer_extra_usage_until_body",
          defaultMessage:
            "Your plan’s limit is reached, so replies use extra usage until {resetsAt, date, ::EEEjmm}.",
        },
        { resetsAt }
      )
}

/** Before the next message, since each reply now costs apart from the plan. */
export function ExtraUsageNotice({ usage }: { usage: ExtraUsage }) {
  return (
    <div
      role="status"
      className="flex items-center gap-2 rounded-t-2xl border border-b-0 bg-muted px-3 pt-1 pb-5 text-xs text-muted-foreground"
    >
      <CircleAlertIcon className="size-4 shrink-0" />
      <p className="min-w-0 flex-1 text-pretty">{said(usage)}</p>
    </div>
  )
}
