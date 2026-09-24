import { DotIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { InUse } from "./your-model-row"

/**
 * Said once, above the groups: the model in use may sit inside a server group
 * that is closed, so its row alone cannot be relied on to say it.
 */
export function InUseSummary({
  slot,
  inUse,
}: {
  slot: string
  inUse: InUse | null
}) {
  return (
    <section
      aria-label={intl.formatMessage(
        {
          id: "models_in_use_summary_aria",
          defaultMessage:
            "{slot, select, chat {chat model in use} image {image model in use} audio {audio model in use} other {model in use}}",
        },
        { slot }
      )}
      className="flex min-w-0 flex-1 items-center gap-2 rounded-lg bg-muted/50 px-3 py-2.5 text-sm"
    >
      <span className="shrink-0 text-muted-foreground">
        {intl.formatMessage({
          id: "models_in_use_summary_label",
          defaultMessage: "In use:",
        })}
      </span>
      {inUse ? (
        <>
          <span className="min-w-0 truncate font-medium">{inUse.name}</span>
          <DotIcon
            aria-hidden="true"
            className="size-3 shrink-0 text-muted-foreground"
          />
          <span className="shrink-0 text-muted-foreground">{inUse.source}</span>
        </>
      ) : (
        <span className="text-muted-foreground">
          {intl.formatMessage(
            {
              id: "models_in_use_summary_empty",
              defaultMessage:
                "{slot, select, chat {No chat model chosen} image {No image model chosen} audio {No audio model chosen} other {No model chosen}}",
            },
            { slot }
          )}
        </span>
      )}
    </section>
  )
}
