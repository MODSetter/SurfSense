import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { intl } from "@/i18n/intl"
import type { PrivacyState } from "@/lib/api"

import { UpdateRequestDetails } from "./update-request-details"
import { UsageReportDetails } from "./usage-report-details"

export type WhatsSentTopic = "updates" | "usage"

function title(topic: WhatsSentTopic) {
  return topic === "updates"
    ? intl.formatMessage({
        id: "privacy_choices_whats_sent_updates_title",
        defaultMessage: "What an update check sends",
      })
    : intl.formatMessage({
        id: "privacy_choices_whats_sent_usage_title",
        defaultMessage: "What usage statistics send",
      })
}

/**
 * A link-styled button that opens exactly what one of the two sends: the update
 * request with its headers, or the usage report's JSON.
 */
export function WhatsSentDialog({
  topic,
  state,
  label,
}: {
  topic: WhatsSentTopic
  state: PrivacyState
  label: string
}) {
  return (
    <Dialog>
      <DialogTrigger
        render={
          <Button
            type="button"
            variant="link"
            className="h-auto w-fit p-0 text-muted-foreground hover:text-foreground"
          />
        }
      >
        {label}
      </DialogTrigger>
      <DialogContent className="max-h-[calc(100%-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title(topic)}</DialogTitle>
        </DialogHeader>
        <ScrollFade className="min-h-0" viewportClassName="pb-1">
          {topic === "updates" ? (
            <UpdateRequestDetails state={state} />
          ) : (
            <UsageReportDetails state={state} />
          )}
        </ScrollFade>
        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  )
}
