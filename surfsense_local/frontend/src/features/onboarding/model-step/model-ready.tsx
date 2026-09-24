import type { InUse } from "@/features/models/your-models/your-model-row"

/** A server's id carries its maker ("aion-labs/aion-2.0"); the server already says whose. */
function shortName(name: string) {
  return name.split("/").at(-1) || name
}

/** Where it runs, phrased to finish the sentence rather than label it. */
function whereItRuns(inUse: InUse) {
  if (inUse.where === "server") return `via ${inUse.source}`
  if (inUse.where === "local") return "on this computer"
  return "(not found on this computer)"
}

/**
 * The slot's model as a sentence beside the button it unlocks: "Using
 * aion-2.0 via OpenRouter". It lives in the footer so the heading never
 * changes shape and the list never moves.
 */
export function ModelReady({ inUse }: { inUse: InUse }) {
  return (
    <section
      aria-label="Model ready"
      title={`${inUse.name} · ${inUse.source}`}
      className="flex min-w-0 items-baseline gap-1 text-sm text-muted-foreground"
    >
      <span className="shrink-0">Using</span>
      <span className="min-w-0 truncate font-medium text-foreground">
        {shortName(inUse.name)}
      </span>
      <span className="shrink-0">{whereItRuns(inUse)}</span>
    </section>
  )
}
