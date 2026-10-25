import { Switch } from "@/components/ui/switch"
import { intl } from "@/i18n/intl"

import { usageText } from "./choice-text"
import { DetailsTooltip } from "./details-tooltip"
import { usageLockedText } from "./locked-text"
import { usePrivacyState } from "./use-privacy-state"
import { WhatsSentDialog } from "./whats-sent-dialog"

/** Settings › About, under App updates: the switch, and exactly what it sends. */
export function UsageStatisticsSettings() {
  const { state, setUsageStatistics } = usePrivacyState()
  if (!state) return null

  const usage = state.usageStatistics
  const text = usageText(state)
  const locked = usageLockedText(state)
  const title = intl.formatMessage({
    id: "privacy_choices_usage_settings_title",
    defaultMessage: "Usage statistics",
  })
  return (
    <div className="mt-8 flex items-start justify-between gap-8">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-1.5">
          <h3 className="text-sm font-medium">{title}</h3>
          <DetailsTooltip label={text.label} details={text.details} />
        </div>
        <p className="text-sm text-pretty text-muted-foreground">
          {text.summary}
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
