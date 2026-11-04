import type { AppendMessage } from "@assistant-ui/react"

type RunConfig = NonNullable<AppendMessage["runConfig"]>

/** One row picked from the `@` list, kept with the composer until it sends. */
export type MentionPick = { id: string; label: string }

/** The API's `mentioned_sources`. An artifact is named by its document. */
export type MentionedSources = {
  document_ids: number[]
  folder_ids: number[]
}

const PICKS = "sourceMentions"
// Past the name, a letter or digit means the user edited it into another word.
const WORD_GOES_ON = /^[\p{L}\p{N}_-]/u

export function picksOf(runConfig: RunConfig | undefined): MentionPick[] {
  return (runConfig?.custom?.[PICKS] as MentionPick[] | undefined) ?? []
}

export function withPick(runConfig: RunConfig, pick: MentionPick): RunConfig {
  return {
    ...runConfig,
    custom: { ...runConfig.custom, [PICKS]: [...picksOf(runConfig), pick] },
  }
}

function stillWritten(text: string, { label }: MentionPick) {
  const written = `@${label}`
  for (
    let at = text.indexOf(written);
    at !== -1;
    at = text.indexOf(written, at + 1)
  ) {
    if (!WORD_GOES_ON.test(text.slice(at + written.length))) return true
  }
  return false
}

/** The ids behind what is still in the text; null when there are none. */
export function namedSources(
  picks: MentionPick[],
  text: string
): MentionedSources | null {
  const named = picks.filter((pick) => stillWritten(text, pick))
  if (named.length === 0) return null
  const idsOf = (kind: string) => [
    ...new Set(
      named.flatMap(({ id }) =>
        id.startsWith(`${kind}:`) ? [Number(id.slice(kind.length + 1))] : []
      )
    ),
  ]
  return { document_ids: idsOf("document"), folder_ids: idsOf("folder") }
}
