import type { ReactNode } from "react"

import type { InUse } from "@/features/models/your-models/your-model-row"
import { intl } from "@/i18n/intl"

/** A server's id carries its maker ("aion-labs/aion-2.0"); the server already says whose. */
function shortName(name: string) {
  return name.split("/").at(-1) || name
}

/** One whole sentence per place it runs, so each language orders it its own way. */
function usingSentence(inUse: InUse) {
  const values = {
    name: shortName(inUse.name),
    b: (chunks: ReactNode[]) => (
      <span className="font-medium text-foreground">{chunks}</span>
    ),
  }
  if (inUse.where === "server") {
    return intl.formatMessage(
      { id: "onboarding_model_ready_server_status" },
      { ...values, source: inUse.source }
    )
  }
  if (inUse.where === "local") {
    return intl.formatMessage(
      { id: "onboarding_model_ready_local_status" },
      values
    )
  }
  return intl.formatMessage(
    { id: "onboarding_model_ready_missing_status" },
    values
  )
}

/**
 * The slot's model as a sentence beside the button it unlocks: "Using
 * aion-2.0 via OpenRouter". It lives in the footer so the heading never
 * changes shape and the list never moves.
 */
export function ModelReady({ inUse }: { inUse: InUse }) {
  return (
    <section
      aria-label={intl.formatMessage({ id: "onboarding_model_ready_aria" })}
      title={`${inUse.name} · ${inUse.source}`}
      className="min-w-0 truncate text-sm text-muted-foreground"
    >
      {usingSentence(inUse)}
    </section>
  )
}
