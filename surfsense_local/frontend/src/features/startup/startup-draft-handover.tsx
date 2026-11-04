import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext"
import { useAui, useAuiState } from "@assistant-ui/react"
import { $getRoot, $isElementNode, $isTextNode } from "lexical"
import { useEffect, useRef } from "react"

import type { StartupDraft } from "./startup-input"
import { useStartupInput } from "./startup-input-context"

function $selectOffset(offset: number) {
  let left = offset
  for (const line of $getRoot().getChildren()) {
    if (!$isElementNode(line)) continue
    for (const child of line.getChildren()) {
      const size = child.getTextContentSize()
      if ($isTextNode(child) && left <= size) {
        child.select(left, left)
        return
      }
      left -= size
    }
    if (left === 0) {
      line.selectEnd()
      return
    }
    left -= 1
  }
  $getRoot().selectEnd()
}

/**
 * Puts what was typed into the startup frame's box into the composer, caret and
 * all. A plugin of the composer's editor, which reports the caret to its `@`
 * trigger, so a mention the caret was left in opens the list as typing it would.
 */
export function StartupDraftHandover({ draft }: { draft: StartupDraft }) {
  const [editor] = useLexicalComposerContext()
  const aui = useAui()
  const startup = useStartupInput()
  const placed = useRef(false)
  const shown = useAuiState(({ composer }) => composer.text === draft.text)

  // After the composer's reset, an earlier sibling's effect, which empties it.
  useEffect(() => {
    startup?.take()
    aui.thread.composer().setText(draft.text)
  }, [aui, draft, startup])

  // Once the text shows: a caret placed before then would land in nothing.
  useEffect(() => {
    if (!shown || placed.current) return
    placed.current = true
    // Focus first: focusing puts a browser's caret at the start of the text.
    editor.getRootElement()?.focus({ preventScroll: true })
    editor.update(() => $selectOffset(draft.caret))
  }, [draft, editor, shown])

  return null
}
