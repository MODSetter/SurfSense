import {
  unstable_useTriggerPopoverRootContextOptional,
  useAui,
  useAuiState,
} from "@assistant-ui/react"
import { useEffect, useRef, type RefObject } from "react"

import { MENTION_TRIGGER } from "@/features/chat/mentions/mention-matcher"

import type { StartupDraft } from "./startup-input"
import { useStartupInput } from "./startup-input-context"

/**
 * Puts what was typed into the startup frame's box into the composer, caret
 * and all. Rendered inside the composer's trigger root, whose `@` trigger
 * keeps its own cursor: it is told where the caret is, so a mention the
 * caret was left in opens the list as typing it would have.
 */
export function StartupDraftHandover({
  draft,
  inputRef,
}: {
  draft: StartupDraft
  inputRef: RefObject<HTMLTextAreaElement | null>
}) {
  const aui = useAui()
  const startup = useStartupInput()
  const triggers = unstable_useTriggerPopoverRootContextOptional()
  const placed = useRef(false)
  const shown = useAuiState(({ composer }) => composer.text === draft.text)

  // After the composer's reset, an earlier sibling's effect, which empties it.
  useEffect(() => {
    startup?.take()
    aui.thread.composer().setText(draft.text)
  }, [aui, draft, startup])

  // Once the text shows: a caret placed before then would land in nothing.
  useEffect(() => {
    const box = inputRef.current
    if (!shown || placed.current || !box) return
    placed.current = true
    box.focus({ preventScroll: true })
    box.setSelectionRange(draft.caret, draft.caret)
    // Absent in Basic chats, which have no `@` list.
    triggers
      ?.getTriggers()
      .get(MENTION_TRIGGER)
      ?.resource.setCursorPosition(draft.caret)
  }, [draft, inputRef, shown, triggers])

  return null
}
