import { useAuiState, type TextMessagePartComponent } from "@assistant-ui/react"

import { MentionIcon } from "./mention-icon"
import { piecesOf, type ShownMention } from "./mention-text"

const NO_MENTIONS: ShownMention[] = []

function mentionsFrom(custom: unknown): ShownMention[] {
  if (typeof custom === "object" && custom !== null && "mentions" in custom) {
    return custom.mentions as ShownMention[]
  }
  return NO_MENTIONS
}

/** A sent message's text, each source it named as a chip. */
export const MentionedText: TextMessagePartComponent = ({ text }) => {
  const mentions = useAuiState(({ message }) =>
    mentionsFrom(message.metadata.custom)
  )
  return (
    <>
      {piecesOf(text, mentions).map((piece, index) =>
        typeof piece === "string" ? (
          piece
        ) : (
          <span
            key={`${piece.id}:${index}`}
            className="inline-flex max-w-full items-baseline gap-1 align-baseline font-medium text-notice"
          >
            <MentionIcon
              id={piece.id}
              type={piece.type}
              className="size-3.5 shrink-0 self-center"
            />
            <span className="truncate">{piece.label}</span>
          </span>
        )
      )}
    </>
  )
}
