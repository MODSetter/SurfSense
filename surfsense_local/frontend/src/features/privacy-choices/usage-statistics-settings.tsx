import { Switch } from "@/components/ui/switch"
import { intl } from "@/i18n/intl"

import { usageLockedText } from "./locked-text"
import { usePrivacyState } from "./use-privacy-state"
import { WhatsSentDialog } from "./whats-sent-dialog"

/** Settings › About, under App updates: the switch, and exactly what it sends. */
export function UsageStatisticsSettings() {
  const { state, setUsageStatistics } = usePrivacyState()
  if (!state) return null

  const usage = state.usageStatistics
  const locked = usageLockedText(state)
  const title = intl.formatMessage({
    id: "privacy_choices_usage_settings_title",
    defaultMessage: "Usage statistics",
  })
  return (
    <div className="mt-8 flex items-start justify-between gap-8">
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-medium">{title}</h3>
        <p className="text-sm text-pretty text-muted-foreground">
          {intl.formatMessage(
            {
              id: "privacy_choices_usage_settings_body",
              defaultMessage:
                "Once a day, tell {host} this install was used, and once a week add counts in ranges, such as how many chats and sources. Never documents, prompts, file names, model names, hosts, your license key or an ID.",
            },
            { host: usage.host }
          )}
        </p>
        {locked ? (
          <p className="text-sm text-muted-foreground">{locked}</p>
        ) : null}
        <WhatsSentDialog
          topic="usage"
          state={state}
          label={intl.formatMessage({
            id: "privacy_choices_usage_settings_whats_sent_button",
            defaultMessage: "Show exactly what’s sent",
          })}
        />
      </div>
      <Switch
        className="mt-0.5"
        checked={usage.enabled === true}
        disabled={usage.locked}
        aria-label={title}
        onCheckedChange={(checked) => void setUsageStatistics(checked)}
      />
    </div>
  )
}
