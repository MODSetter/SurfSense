import type { ReactNode } from "react"

import type { InUse } from "@/features/models/your-models/your-model-row"
import { intl } from "@/i18n/intl"

/** A server's id carries its maker ("aion-labs/aion-2.0"); the server already says whose. */
function shortName(name: string) {
  return name.split("/").at(-1) || name
}

const bold = (chunks: ReactNode[]) => (
  <span className="font-medium text-foreground">{chunks}</span>
)

/** One whole sentence per place it runs, so each language orders it its own way. */
function usingSentence(inUse: InUse) {
  // Each call writes its values out: the lint reads placeholders only from a literal.
  const name = shortName(inUse.name)
  if (inUse.where === "server") {
    return intl.formatMessage(
      {
        id: "onboarding_model_ready_server_status",
        defaultMessage: "Using <b>{name}</b> via {source}",
      },
      { name, b: bold, source: inUse.source }
    )
  }
  if (inUse.where === "local") {
    return intl.formatMessage(
      {
        id: "onboarding_model_ready_local_status",
        defaultMessage: "Using <b>{name}</b> on this computer",
      },
      { name, b: bold }
    )
  }
  return intl.formatMessage(
    {
      id: "onboarding_model_ready_missing_status",
      defaultMessage: "Using <b>{name}</b> (not found on this computer)",
    },
    { name, b: bold }
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
      aria-label={intl.formatMessage({
        id: "onboarding_model_ready_aria",
        defaultMessage: "Model ready",
      })}
      title={`${inUse.name} · ${inUse.source}`}
      className="min-w-0 truncate text-sm text-muted-foreground"
    >
      {usingSentence(inUse)}
    </section>
  )
}
