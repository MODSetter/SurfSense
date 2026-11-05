import { useEffect, useState } from "react"

import {
  ComposerBox,
  ComposerColumn,
  ComposerControls,
  ComposerText,
} from "@/features/chat/composer-surface"
import {
  messageLabel,
  startPlaceholder,
} from "@/features/chat/composer-wording"
import { QUESTION_MAX_CHARS } from "@/features/chat/question-limit"
import { MentionListSkeleton } from "@/features/chat/mentions/mention-list-skeleton"
import {
  MENTION_TRIGGER,
  mentionAt,
} from "@/features/chat/mentions/mention-matcher"

import { useStartupInput } from "./startup-input-context"

/**
 * A new chat's box while the app loads: it takes typing, keeps it for the
 * composer that replaces it, and sends nothing, having nowhere to send yet.
 * `mentions` is whether `@` names sources in the chat it will become.
 */
export function StartupComposer({ mentions }: { mentions: boolean }) {
  const startup = useStartupInput()
  const [text, setText] = useState("")
  const [caret, setCaret] = useState(0)

  // A box gone mid-composition must not hold startup's end.
  useEffect(() => () => startup?.setComposing(false), [startup])

  const track = (box: HTMLTextAreaElement) => {
    setText(box.value)
    setCaret(box.selectionStart)
    startup?.keep(box.value, box.selectionStart)
  }

  return (
    <ComposerColumn data-composer-outline="center">
      <ComposerBox placement="center">
        {mentions && mentionAt(text, MENTION_TRIGGER, caret) ? (
          <MentionListSkeleton />
        ) : null}
        <ComposerText
          placement="center"
          // As the composer it stands for does.
          autoFocus
          aria-label={messageLabel()}
          placeholder={startPlaceholder()}
          maxLength={QUESTION_MAX_CHARS}
          onChange={(event) => track(event.currentTarget)}
          onSelect={(event) => track(event.currentTarget)}
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing
            ) {
              event.preventDefault()
            }
          }}
          onCompositionStart={() => startup?.setComposing(true)}
          onCompositionEnd={(event) => {
            startup?.setComposing(false)
            track(event.currentTarget)
          }}
        />
        <ComposerControls />
      </ComposerBox>
    </ComposerColumn>
  )
}
