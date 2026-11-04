import { defaultDirectiveFormatter } from "@assistant-ui/react"

/** A chip in a sent message: what it names, and where it stands in the text. Its
 *  place is all that tells it from the same name typed by hand. */
export type ShownMention = {
  id: string
  type: string
  label: string
  at: number
  length: number
}

/** The API's `mentioned_sources`. An artifact is named by its document. */
export type MentionedSources = {
  document_ids: number[]
  folder_ids: number[]
  chips: { id: string; at: number; length: number }[]
}

const isMentionType = (type: string) =>
  type === "source" || type.startsWith("artifact-")

const TRIGGER = "@"

/** The box's text, which holds each chip's id so a rewrite of the text can rebuild
 *  it, as it is sent: what the user reads, and each chip's place in that. */
export function sentMessage(raw: string): {
  text: string
  mentions: ShownMention[]
} {
  const mentions: ShownMention[] = []
  let text = ""
  for (const segment of defaultDirectiveFormatter.parse(raw)) {
    if (segment.kind === "text") {
      text += segment.text
    } else if (!isMentionType(segment.type)) {
      text += defaultDirectiveFormatter.serialize(segment)
    } else {
      const { id, type, label } = segment
      const written = `${TRIGGER}${label}`
      mentions.push({
        id,
        type,
        label,
        at: text.length,
        length: written.length,
      })
      text += written
    }
  }
  return { text, mentions }
}

/** What counts against the message limit: never a chip's hidden id. */
export function messageLength(raw: string) {
  return sentMessage(raw).text.length
}

export function mentionedSourcesOf(
  mentions: readonly ShownMention[]
): MentionedSources | null {
  if (mentions.length === 0) return null
  const idsOf = (kind: string) => [
    ...new Set(
      mentions.flatMap(({ id }) =>
        id.startsWith(`${kind}:`) ? [Number(id.slice(kind.length + 1))] : []
      )
    ),
  ]
  return {
    document_ids: idsOf("document"),
    folder_ids: idsOf("folder"),
    chips: mentions.map(({ id, at, length }) => ({ id, at, length })),
  }
}

/** A refused message's text, back as the box holds it, so its chips return too. */
export function boxTextOf(text: string, mentions: readonly ShownMention[]) {
  return piecesOf(text, mentions)
    .map((piece) =>
      typeof piece === "string"
        ? piece
        : defaultDirectiveFormatter.serialize(piece)
    )
    .join("")
}

export type MentionedTextPiece = string | ShownMention

/** A sent message's text, with each chip apart. A place that no longer fits the text
 *  stays text: better a plain `@name` than a chip on the wrong words. */
export function piecesOf(
  text: string,
  mentions: readonly ShownMention[]
): MentionedTextPiece[] {
  const pieces: MentionedTextPiece[] = []
  let from = 0
  for (const mention of [...mentions].sort((a, b) => a.at - b.at)) {
    const fits =
      mention.at >= from &&
      mention.at + mention.length <= text.length &&
      text.startsWith(TRIGGER, mention.at)
    if (!fits) continue
    if (mention.at > from) pieces.push(text.slice(from, mention.at))
    pieces.push(mention)
    from = mention.at + mention.length
  }
  if (from < text.length) pieces.push(text.slice(from))
  return pieces
}
