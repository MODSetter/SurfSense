import { useEffect, useState } from "react"

import { Skeleton } from "@/components/ui/skeleton"
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
import {
  MentionItem,
  MentionItemDescription,
  MentionList,
} from "@/features/plugins/in-thread/mention-list"
import {
  MENTION_TRIGGER,
  mentionAt,
} from "@/features/plugins/in-thread/mention-matcher"
import { cn } from "@/lib/utils"

import { useStartupInput } from "./startup-input-context"

// A name and a line about it per row, so the rows read as a list, not a block.
const SKELETON_ROWS = [
  ["w-24", "w-40"],
  ["w-16", "w-32"],
  ["w-28", "w-36"],
] as const

/** The `@` list while the plugins load, drawn as the real one is. */
function MentionListSkeleton() {
  return (
    // Busy, with nothing to pick yet: a group, not a listbox of no options.
    <MentionList role="group" aria-busy="true">
      {SKELETON_ROWS.map(([name, about]) => (
        <MentionItem key={name} aria-hidden="true">
          {/* One line of the row's own text tall, whatever its size. */}
          <span className="flex h-lh items-center">
            <Skeleton className={cn("h-[0.7lh]", name)} />
          </span>
          <MentionItemDescription className="flex h-lh items-center">
            <Skeleton className={cn("h-[0.7lh]", about)} />
          </MentionItemDescription>
        </MentionItem>
      ))}
    </MentionList>
  )
}

/**
 * A new chat's box while the app loads: it takes typing, keeps it for the
 * composer that replaces it, and sends nothing, having nowhere to send yet.
 * `mentions` is whether `@` names plugins in the chat it will become.
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
