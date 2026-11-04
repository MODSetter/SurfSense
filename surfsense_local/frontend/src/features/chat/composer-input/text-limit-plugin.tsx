import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext"
import { $getSelection, $isRangeSelection, $isTextNode, RootNode } from "lexical"
import { useEffect } from "react"

import { messageLength } from "../mentions/mention-text"

/** Past the limit, what was just written is cut back from the caret: typing, a paste
 *  and an input method alike. Counts what the user reads, never a chip's hidden id. */
export function TextLimitPlugin({ max }: { max: number }) {
  const [editor] = useLexicalComposerContext()
  useEffect(
    () =>
      editor.registerNodeTransform(RootNode, (root) => {
        const over = messageLength(root.getTextContent()) - max
        const selection = $getSelection()
        if (over <= 0 || !$isRangeSelection(selection)) return
        const { offset } = selection.anchor
        const written = selection.anchor.getNode()
        const cut = Math.min(over, offset)
        if ($isTextNode(written) && selection.isCollapsed() && cut > 0) {
          written.spliceText(offset - cut, cut, "", true)
        }
      }),
    [editor, max]
  )
  return null
}
