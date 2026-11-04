import { defaultDirectiveFormatter } from "@assistant-ui/react"

/** A named source as the box's chip and the sent bubble's show it. */
export type ShownMention = { id: string; type: string; label: string }

/** The API's `mentioned_sources`. An artifact is named by its document. */
export type MentionedSources = {
  document_ids: number[]
  folder_ids: number[]
}

const isMentionType = (type: string) =>
  type === "source" || type.startsWith("artifact-")

const written = (label: string) => `@${label}`

/** The box's text, which holds each chip's id so a rewrite of the text can rebuild
 *  it, as it is sent: what the user reads, and what it named beside that. */
export function sentMessage(raw: string): {
  text: string
  mentions: ShownMention[]
} {
  const mentions = new Map<string, ShownMention>()
  const text = defaultDirectiveFormatter
    .parse(raw)
    .map((segment) => {
      if (segment.kind === "text") return segment.text
      if (!isMentionType(segment.type)) {
        return defaultDirectiveFormatter.serialize(segment)
      }
      const { id, type, label } = segment
      mentions.set(id, { id, type, label })
      return written(label)
    })
    .join("")
  return { text, mentions: [...mentions.values()] }
}

/** What counts against the message limit: never a chip's hidden id. */
export function messageLength(raw: string) {
  return sentMessage(raw).text.length
}

export function mentionedSourcesOf(
  mentions: readonly ShownMention[]
): MentionedSources | null {
  if (mentions.length === 0) return null
  const idsOf = (kind: string) =>
    mentions.flatMap(({ id }) =>
      id.startsWith(`${kind}:`) ? [Number(id.slice(kind.length + 1))] : []
    )
  return { document_ids: idsOf("document"), folder_ids: idsOf("folder") }
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

// Past the name, a letter or digit means another word that starts the same.
const WORD_GOES_ON = /^[\p{L}\p{N}_-]/u

/** A sent message's text, with each named source apart for its chip. */
export function piecesOf(
  text: string,
  mentions: readonly ShownMention[]
): MentionedTextPiece[] {
  // The longest first, so "@Plan" never takes the start of "@Plan Q3".
  const longestFirst = [...mentions].sort(
    (a, b) => b.label.length - a.label.length
  )
  const pieces: MentionedTextPiece[] = []
  let plain = ""
  for (let at = 0; at < text.length;) {
    const found = longestFirst.find(
      ({ label }) =>
        text.startsWith(written(label), at) &&
        !WORD_GOES_ON.test(text.slice(at + written(label).length))
    )
    if (found) {
      if (plain) pieces.push(plain)
      plain = ""
      pieces.push(found)
      at += written(found.label).length
    } else {
      plain += text[at]
      at += 1
    }
  }
  if (plain) pieces.push(plain)
  return pieces
}
