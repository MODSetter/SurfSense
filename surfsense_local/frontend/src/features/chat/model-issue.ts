import { intl } from "@/i18n/intl"
import type { ModelIssue } from "@/features/models/selection/availability"

// The composer's placeholder while egress holds it: the notice above says why.
export function consentPlaceholder(issue: ModelIssue): string {
  return intl.formatMessage(
    {
      id: "chat_composer_egress_off_placeholder",
      defaultMessage: "Allow sending to {host} to chat",
    },
    { host: issue.host ?? issue.model }
  )
}
